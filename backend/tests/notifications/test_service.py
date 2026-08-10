from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlmodel import Session, select

from app import crud
from app.models import UserCreate
from app.notifications import repository, service
from app.notifications.models import NotificationOutbox
from tests.utils.utils import random_email, random_lower_string


def enqueue_notification(db: Session) -> NotificationOutbox:
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )
    notification = repository.enqueue_user_registered(session=db, user=user)
    db.commit()
    db.refresh(notification)
    return notification


def test_worker_publishes_notification(db: Session) -> None:
    notification = enqueue_notification(db)

    with (
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.EMAILS_FROM_EMAIL", "noreply@example.com"),
        patch("app.notifications.service.send_email") as send_email,
    ):
        assert service.process_next(session=db) is True

    db.refresh(notification)
    assert notification.published_at is not None
    send_email.assert_called_once()
    assert send_email.call_args.kwargs["email_to"] == notification.payload["email"]


def test_smtp_failure_leaves_notification_unpublished(db: Session) -> None:
    notification = enqueue_notification(db)

    with (
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.EMAILS_FROM_EMAIL", "noreply@example.com"),
        patch(
            "app.notifications.service.send_email",
            side_effect=RuntimeError("SMTP unavailable"),
        ),
        pytest.raises(RuntimeError, match="SMTP unavailable"),
    ):
        service.process_next(session=db)

    db.rollback()
    persisted = db.exec(
        select(NotificationOutbox).where(NotificationOutbox.id == notification.id)
    ).one()
    assert persisted.published_at is None


def test_unsuccessful_smtp_response_leaves_notification_unpublished(
    db: Session,
) -> None:
    notification = enqueue_notification(db)
    response = SimpleNamespace(
        success=False, status_code=550, status_text="mailbox unavailable"
    )

    with (
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.EMAILS_FROM_EMAIL", "noreply@example.com"),
        patch("app.utils.emails.Message.send", return_value=response),
        pytest.raises(RuntimeError, match="Email delivery failed"),
    ):
        service.process_next(session=db)

    db.rollback()
    persisted = db.exec(
        select(NotificationOutbox).where(NotificationOutbox.id == notification.id)
    ).one()
    assert persisted.published_at is None


def test_worker_does_nothing_when_email_is_disabled(db: Session) -> None:
    notification = enqueue_notification(db)

    with (
        patch("app.core.config.settings.SMTP_HOST", None),
        patch("app.notifications.service.send_email") as send_email,
    ):
        assert service.process_next(session=db) is False

    db.refresh(notification)
    assert notification.published_at is None
    send_email.assert_not_called()
