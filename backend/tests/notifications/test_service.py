from unittest.mock import patch

from app.notifications import service


def test_consumer_routes_registered_user_event() -> None:
    payload = {"email": "new-user@example.com"}

    with (
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.EMAILS_FROM_EMAIL", "noreply@example.com"),
        patch(
            "app.notifications.service.deliver_welcome_email", return_value=True
        ) as deliver,
    ):
        assert service.handle_event("user_registered", payload) is True

    deliver.assert_called_once_with(payload=payload)


def test_consumer_ignores_unhandled_event() -> None:
    with patch("app.notifications.service.deliver_welcome_email") as deliver:
        assert service.handle_event("file_shared", {"email": "user@example.com"})

    deliver.assert_not_called()


def test_consumer_respects_disabled_email_setting() -> None:
    with (
        patch("app.core.config.settings.SMTP_HOST", None),
        patch("app.notifications.service.deliver_welcome_email") as deliver,
    ):
        assert (
            service.handle_event("user_registered", {"email": "new-user@example.com"})
            is False
        )

    deliver.assert_not_called()


def test_consumer_tolerates_duplicate_delivery() -> None:
    payload = {"email": "new-user@example.com"}

    with (
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.EMAILS_FROM_EMAIL", "noreply@example.com"),
        patch(
            "app.notifications.service.deliver_welcome_email", return_value=True
        ) as deliver,
    ):
        assert service.handle_event("user_registered", payload) is True
        assert service.handle_event("user_registered", payload) is True

    assert deliver.call_count == 2


def test_consumer_retries_failed_delivery() -> None:
    with (
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.EMAILS_FROM_EMAIL", "noreply@example.com"),
        patch("app.notifications.service.deliver_welcome_email", return_value=False),
    ):
        assert (
            service.handle_event("user_registered", {"email": "new-user@example.com"})
            is False
        )
