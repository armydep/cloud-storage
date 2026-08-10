import logging
from typing import Any, cast

from app.core.config import settings
from app.notifications.events import FILE_SHARED, USER_REGISTERED
from app.utils import EmailData, render_email_template, send_email

logger = logging.getLogger(__name__)


def generate_welcome_email(*, email_to: str) -> EmailData:
    return EmailData(
        subject=f"{settings.PROJECT_NAME} - Welcome",
        html_content=render_email_template(
            template_name="welcome.html",
            context={
                "project_name": settings.PROJECT_NAME,
                "email": email_to,
                "link": settings.FRONTEND_HOST,
            },
        ),
    )


def deliver_welcome_email(*, payload: dict[str, Any]) -> bool:
    email_to = cast(str, payload["email"])
    email = generate_welcome_email(email_to=email_to)
    return send_email(
        email_to=email_to,
        subject=email.subject,
        html_content=email.html_content,
    )


def generate_file_shared_email(*, sharer_email: str, file_name: str) -> EmailData:
    return EmailData(
        subject=f"{settings.PROJECT_NAME} - {sharer_email} shared a file with you",
        html_content=render_email_template(
            template_name="file_shared.html",
            context={
                "project_name": settings.PROJECT_NAME,
                "sharer_email": sharer_email,
                "file_name": file_name,
                "link": settings.FRONTEND_HOST,
            },
        ),
    )


def deliver_file_shared_email(*, payload: dict[str, Any]) -> bool:
    email_to = cast(str, payload["recipient_email"])
    sharer_email = cast(str, payload["sharer_email"])
    file_name = cast(str, payload["file_name"])
    email = generate_file_shared_email(sharer_email=sharer_email, file_name=file_name)
    return send_email(
        email_to=email_to,
        subject=email.subject,
        html_content=email.html_content,
    )


def handle_event(event_type: str, payload: dict[str, Any], _message_id: str) -> bool:
    if event_type == USER_REGISTERED:
        if not settings.emails_enabled:
            return False
        if not isinstance(payload.get("email"), str):
            return False
        return deliver_welcome_email(payload=payload)

    if event_type == FILE_SHARED:
        if not settings.emails_enabled:
            return False
        if not all(
            isinstance(payload.get(key), str)
            for key in ("recipient_email", "sharer_email", "file_name")
        ):
            return False
        return deliver_file_shared_email(payload=payload)

    logger.info("Ignoring unsupported notification event: %s", event_type)
    return True
