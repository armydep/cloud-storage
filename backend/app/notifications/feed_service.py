import base64
import binascii
import logging
import uuid
from datetime import datetime
from typing import Any

from sqlmodel import Session

from app.notifications import repository
from app.notifications.events import FILE_SHARED
from app.notifications.models import Notification
from app.notifications.schemas import (
    NotificationPublic,
    NotificationsPublic,
    UnreadCountPublic,
)

logger = logging.getLogger(__name__)

# user_registered is deliberately excluded (design decision 8): only events
# useful after the fact belong in the feed, and q.inapp is only bound to
# these routing keys in the first place.
FEED_EVENT_TYPES = {FILE_SHARED}


class NotificationNotFoundError(Exception):
    pass


class InvalidCursorError(Exception):
    pass


def handle_event(
    *, session: Session, event_type: str, payload: dict[str, Any], message_id: str
) -> bool:
    if event_type not in FEED_EVENT_TYPES:
        logger.info("Ignoring unsupported feed event: %s", event_type)
        return True

    try:
        outbox_id = uuid.UUID(message_id)
    except ValueError:
        logger.error("Notification message missing a valid outbox id: %r", message_id)
        return False

    recipient_id_raw = payload.get("recipient_id")
    if not isinstance(recipient_id_raw, str):
        return False
    try:
        recipient_id = uuid.UUID(recipient_id_raw)
    except ValueError:
        return False

    repository.insert_notification(
        session=session,
        outbox_id=outbox_id,
        user_id=recipient_id,
        event_type=event_type,
        payload=payload,
    )
    session.commit()
    return True


def _encode_cursor(*, created_at: datetime, notification_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{notification_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        created_at_str, id_str = raw.rsplit("|", 1)
        return datetime.fromisoformat(created_at_str), uuid.UUID(id_str)
    except (ValueError, binascii.Error) as exc:
        raise InvalidCursorError from exc


def _to_public(notification: Notification) -> NotificationPublic:
    return NotificationPublic(
        id=notification.id,
        event_type=notification.event_type,
        payload=notification.payload,
        created_at=notification.created_at,
        read_at=notification.read_at,
    )


def list_notifications(
    *,
    session: Session,
    user_id: uuid.UUID,
    limit: int,
    cursor: str | None,
    unread_only: bool,
) -> NotificationsPublic:
    decoded_cursor = _decode_cursor(cursor) if cursor else None
    notifications = repository.list_notifications(
        session=session,
        user_id=user_id,
        limit=limit,
        cursor=decoded_cursor,
        unread_only=unread_only,
    )
    next_cursor = None
    if len(notifications) == limit:
        last = notifications[-1]
        next_cursor = _encode_cursor(
            created_at=last.created_at, notification_id=last.id
        )
    return NotificationsPublic(
        data=[_to_public(notification) for notification in notifications],
        next_cursor=next_cursor,
    )


def unread_count(*, session: Session, user_id: uuid.UUID) -> UnreadCountPublic:
    return UnreadCountPublic(
        count=repository.count_unread(session=session, user_id=user_id)
    )


def mark_read(
    *, session: Session, user_id: uuid.UUID, notification_id: uuid.UUID
) -> NotificationPublic:
    notification = repository.get_notification_by_id(
        session=session, user_id=user_id, notification_id=notification_id
    )
    if notification is None:
        raise NotificationNotFoundError
    repository.mark_notification_read(session=session, notification=notification)
    return _to_public(notification)


def mark_all_read(*, session: Session, user_id: uuid.UUID) -> None:
    repository.mark_all_read(session=session, user_id=user_id)
