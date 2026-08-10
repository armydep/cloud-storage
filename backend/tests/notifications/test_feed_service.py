import uuid

import pytest
from sqlmodel import Session, select

from app import crud
from app.models import UserCreate
from app.notifications import feed_service, repository
from app.notifications.events import FILE_SHARED
from app.notifications.models import Notification
from tests.utils.utils import random_email, random_lower_string


def _create_user(db: Session):
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )
    db.commit()
    return user


def test_handle_event_inserts_notification_for_file_shared(db: Session) -> None:
    recipient = _create_user(db)
    outbox = repository.enqueue_file_shared(
        session=db,
        file_id=uuid.uuid4(),
        file_name="report.pdf",
        recipient_id=recipient.id,
        recipient_email=recipient.email,
        sharer_email="alice@example.com",
    )
    db.commit()

    assert (
        feed_service.handle_event(
            session=db,
            event_type=FILE_SHARED,
            payload=outbox.payload,
            message_id=str(outbox.id),
        )
        is True
    )

    notification = db.exec(
        select(Notification).where(Notification.outbox_id == outbox.id)
    ).one()
    assert notification.user_id == recipient.id
    assert notification.event_type == FILE_SHARED
    assert notification.read_at is None


def test_handle_event_duplicate_delivery_is_a_noop(db: Session) -> None:
    recipient = _create_user(db)
    outbox = repository.enqueue_file_shared(
        session=db,
        file_id=uuid.uuid4(),
        file_name="report.pdf",
        recipient_id=recipient.id,
        recipient_email=recipient.email,
        sharer_email="alice@example.com",
    )
    db.commit()

    for _ in range(2):
        assert (
            feed_service.handle_event(
                session=db,
                event_type=FILE_SHARED,
                payload=outbox.payload,
                message_id=str(outbox.id),
            )
            is True
        )

    rows = db.exec(
        select(Notification).where(Notification.outbox_id == outbox.id)
    ).all()
    assert len(rows) == 1


def test_handle_event_ignores_unsupported_event(db: Session) -> None:
    assert (
        feed_service.handle_event(
            session=db,
            event_type="user_registered",
            payload={"email": "someone@example.com"},
            message_id=str(uuid.uuid4()),
        )
        is True
    )


def test_handle_event_rejects_invalid_message_id(db: Session) -> None:
    recipient = _create_user(db)

    assert (
        feed_service.handle_event(
            session=db,
            event_type=FILE_SHARED,
            payload={"recipient_id": str(recipient.id)},
            message_id="not-a-uuid",
        )
        is False
    )


def test_handle_event_rejects_missing_recipient_id(db: Session) -> None:
    assert (
        feed_service.handle_event(
            session=db,
            event_type=FILE_SHARED,
            payload={},
            message_id=str(uuid.uuid4()),
        )
        is False
    )


def test_list_notifications_rejects_invalid_cursor(db: Session) -> None:
    recipient = _create_user(db)

    with pytest.raises(feed_service.InvalidCursorError):
        feed_service.list_notifications(
            session=db,
            user_id=recipient.id,
            limit=10,
            cursor="not-a-valid-cursor!!",
            unread_only=False,
        )


def test_mark_read_raises_for_missing_notification(db: Session) -> None:
    recipient = _create_user(db)

    with pytest.raises(feed_service.NotificationNotFoundError):
        feed_service.mark_read(
            session=db, user_id=recipient.id, notification_id=uuid.uuid4()
        )
