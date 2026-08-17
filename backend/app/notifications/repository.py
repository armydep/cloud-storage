import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.models import User, get_datetime_utc
from app.notifications.events import (
    FILE_CREATED,
    FILE_DELETED,
    FILE_SHARED,
    FOLDER_DELETED,
    USER_REGISTERED,
)
from app.notifications.models import Notification, NotificationOutbox


def enqueue_user_registered(*, session: Session, user: User) -> NotificationOutbox:
    notification = NotificationOutbox(
        event_type=USER_REGISTERED,
        payload={"user_id": str(user.id), "email": user.email},
    )
    session.add(notification)
    session.flush()
    return notification


def enqueue_file_shared(
    *,
    session: Session,
    file_id: uuid.UUID,
    file_name: str,
    recipient_id: uuid.UUID,
    recipient_email: str,
    sharer_email: str,
) -> NotificationOutbox:
    notification = NotificationOutbox(
        event_type=FILE_SHARED,
        payload={
            "file_id": str(file_id),
            "file_name": file_name,
            "recipient_id": str(recipient_id),
            "recipient_email": recipient_email,
            "sharer_email": sharer_email,
        },
    )
    session.add(notification)
    session.flush()
    return notification


def enqueue_file_created(
    *,
    session: Session,
    file_id: uuid.UUID,
    owner_id: uuid.UUID,
    name: str,
    folder_path: str,
    mime_type: str,
    category: str,
    size_bytes: int,
    created_at: datetime,
) -> NotificationOutbox:
    """Enqueue for search-svc's indexer. The index is fully denormalized

    (design doc, Option A), so every field the indexer needs to write a
    document is carried here -- it must never need a second lookup.
    """
    notification = NotificationOutbox(
        event_type=FILE_CREATED,
        payload={
            "file_id": str(file_id),
            "owner_id": str(owner_id),
            "name": name,
            "folder_path": folder_path,
            "mime_type": mime_type,
            "category": category,
            "size_bytes": size_bytes,
            "created_at": created_at.isoformat(),
        },
    )
    session.add(notification)
    session.flush()
    return notification


def enqueue_file_deleted(
    *, session: Session, file_id: uuid.UUID, owner_id: uuid.UUID
) -> NotificationOutbox:
    notification = NotificationOutbox(
        event_type=FILE_DELETED,
        payload={"file_id": str(file_id), "owner_id": str(owner_id)},
    )
    session.add(notification)
    session.flush()
    return notification


def enqueue_folder_deleted(
    *, session: Session, owner_id: uuid.UUID, folder_path: str
) -> NotificationOutbox:
    """One event for the whole subtree -- never one event per descendant file.

    The indexer expands it with a server-side delete_by_query on owner_id and
    a folder_path prefix (design doc constraint 4); emitting per-file events
    here would produce a burst proportional to subtree size.
    """
    notification = NotificationOutbox(
        event_type=FOLDER_DELETED,
        payload={"owner_id": str(owner_id), "folder_path": folder_path},
    )
    session.add(notification)
    session.flush()
    return notification


def claim_next_unpublished(*, session: Session) -> NotificationOutbox | None:
    statement = (
        select(NotificationOutbox)
        .where(col(NotificationOutbox.published_at).is_(None))
        .order_by(col(NotificationOutbox.created_at), col(NotificationOutbox.id))
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    return session.exec(statement).first()


def insert_notification(
    *,
    session: Session,
    outbox_id: uuid.UUID,
    user_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
) -> Notification | None:
    """Insert a feed row, treating a duplicate `outbox_id` as a no-op.

    Phase 8 delivery is at-least-once, so the in-app consumer will eventually
    see the same event twice; the unique constraint on `outbox_id` is what
    makes redelivery safe here.
    """
    notification = Notification(
        outbox_id=outbox_id,
        user_id=user_id,
        event_type=event_type,
        payload=payload,
    )
    session.add(notification)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return None
    return notification


def list_notifications(
    *,
    session: Session,
    user_id: uuid.UUID,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None = None,
    unread_only: bool = False,
) -> list[Notification]:
    statement = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        statement = statement.where(col(Notification.read_at).is_(None))
    if cursor is not None:
        cursor_created_at, cursor_id = cursor
        statement = statement.where(
            or_(
                col(Notification.created_at) < cursor_created_at,
                and_(
                    col(Notification.created_at) == cursor_created_at,
                    col(Notification.id) < cursor_id,
                ),
            )
        )
    statement = statement.order_by(
        col(Notification.created_at).desc(), col(Notification.id).desc()
    ).limit(limit)
    return list(session.exec(statement).all())


def count_unread(*, session: Session, user_id: uuid.UUID) -> int:
    statement = (
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == user_id,
            col(Notification.read_at).is_(None),
        )
    )
    return session.exec(statement).one()


def get_notification_by_id(
    *, session: Session, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification | None:
    statement = select(Notification).where(
        Notification.user_id == user_id,
        Notification.id == notification_id,
    )
    return session.exec(statement).first()


def mark_notification_read(*, session: Session, notification: Notification) -> None:
    if notification.read_at is not None:
        return
    notification.read_at = get_datetime_utc()
    session.add(notification)
    session.commit()
    session.refresh(notification)


def mark_all_read(*, session: Session, user_id: uuid.UUID) -> None:
    statement = (
        select(Notification)
        .where(Notification.user_id == user_id, col(Notification.read_at).is_(None))
        .with_for_update()
    )
    now = get_datetime_utc()
    for notification in session.exec(statement).all():
        notification.read_at = now
        session.add(notification)
    session.commit()
