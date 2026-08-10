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
        assert service.handle_event("user_registered", payload, "outbox-1") is True

    deliver.assert_called_once_with(payload=payload)


def test_consumer_routes_file_shared_event() -> None:
    payload = {
        "recipient_email": "bob@example.com",
        "sharer_email": "alice@example.com",
        "file_name": "report.pdf",
        "file_id": "11111111-1111-1111-1111-111111111111",
        "recipient_id": "22222222-2222-2222-2222-222222222222",
    }

    with (
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.EMAILS_FROM_EMAIL", "noreply@example.com"),
        patch(
            "app.notifications.service.deliver_file_shared_email", return_value=True
        ) as deliver,
    ):
        assert service.handle_event("file_shared", payload, "outbox-2") is True

    deliver.assert_called_once_with(payload=payload)


def test_consumer_ignores_unhandled_event() -> None:
    with (
        patch("app.notifications.service.deliver_welcome_email") as deliver_welcome,
        patch("app.notifications.service.deliver_file_shared_email") as deliver_shared,
    ):
        assert service.handle_event(
            "some_other_event", {"email": "user@example.com"}, "outbox-3"
        )

    deliver_welcome.assert_not_called()
    deliver_shared.assert_not_called()


def test_consumer_respects_disabled_email_setting() -> None:
    with (
        patch("app.core.config.settings.SMTP_HOST", None),
        patch("app.notifications.service.deliver_welcome_email") as deliver,
    ):
        assert (
            service.handle_event(
                "user_registered", {"email": "new-user@example.com"}, "outbox-4"
            )
            is False
        )

    deliver.assert_not_called()


def test_consumer_rejects_file_shared_with_missing_fields() -> None:
    with (
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.EMAILS_FROM_EMAIL", "noreply@example.com"),
        patch("app.notifications.service.deliver_file_shared_email") as deliver,
    ):
        assert (
            service.handle_event(
                "file_shared", {"recipient_email": "bob@example.com"}, "outbox-5"
            )
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
        assert service.handle_event("user_registered", payload, "outbox-6") is True
        assert service.handle_event("user_registered", payload, "outbox-6") is True

    assert deliver.call_count == 2


def test_consumer_retries_failed_delivery() -> None:
    with (
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.EMAILS_FROM_EMAIL", "noreply@example.com"),
        patch("app.notifications.service.deliver_welcome_email", return_value=False),
    ):
        assert (
            service.handle_event(
                "user_registered", {"email": "new-user@example.com"}, "outbox-7"
            )
            is False
        )


def test_generate_file_shared_email_renders_template() -> None:
    email = service.generate_file_shared_email(
        sharer_email="alice@example.com",
        file_name="report.pdf",
    )

    assert "alice@example.com" in email.html_content
    assert "report.pdf" in email.html_content
    assert "alice@example.com" in email.subject


def test_deliver_file_shared_email_sends_to_recipient() -> None:
    payload = {
        "recipient_email": "bob@example.com",
        "sharer_email": "alice@example.com",
        "file_name": "report.pdf",
    }

    with patch("app.notifications.service.send_email", return_value=True) as send:
        assert service.deliver_file_shared_email(payload=payload) is True

    assert send.call_args.kwargs["email_to"] == "bob@example.com"
