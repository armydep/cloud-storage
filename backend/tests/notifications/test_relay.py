from typing import Any

import pytest
from sqlmodel import Session, delete, select

from app import crud
from app.models import UserCreate
from app.notifications import relay, repository
from app.notifications.models import NotificationOutbox
from tests.utils.utils import random_email, random_lower_string


class RecordingPublisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.published: list[dict[str, Any]] = []

    def publish(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        message_id: str,
    ) -> None:
        if self.fail:
            raise RuntimeError("publish was not confirmed")
        self.published.append(
            {
                "event_type": event_type,
                "payload": payload,
                "message_id": message_id,
            }
        )


def enqueue_notification(db: Session) -> NotificationOutbox:
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )
    notification = repository.enqueue_user_registered(session=db, user=user)
    db.commit()
    db.refresh(notification)
    return notification


def test_relay_publishes_then_marks_notification(db: Session) -> None:
    notification = enqueue_notification(db)
    publisher = RecordingPublisher()

    assert relay.process_next(session=db, publisher=publisher) is True

    db.refresh(notification)
    assert notification.published_at is not None
    assert publisher.published == [
        {
            "event_type": notification.event_type,
            "payload": notification.payload,
            "message_id": str(notification.id),
        }
    ]


def test_relay_leaves_row_unpublished_without_confirm(db: Session) -> None:
    notification = enqueue_notification(db)
    publisher = RecordingPublisher(fail=True)

    with pytest.raises(RuntimeError, match="not confirmed"):
        relay.process_next(session=db, publisher=publisher)

    db.rollback()
    persisted = db.exec(
        select(NotificationOutbox).where(NotificationOutbox.id == notification.id)
    ).one()
    assert persisted.published_at is None


def test_relay_returns_false_when_outbox_is_empty(db: Session) -> None:
    db.exec(delete(NotificationOutbox))
    db.commit()
    publisher = RecordingPublisher()

    assert relay.process_next(session=db, publisher=publisher) is False
    assert publisher.published == []
