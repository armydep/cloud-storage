import logging
from typing import Any, cast

from app.core.config import settings
from app.notifications.events import USER_REGISTERED
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


def handle_event(event_type: str, payload: dict[str, Any]) -> bool:
    if event_type != USER_REGISTERED:
        logger.info("Ignoring unsupported notification event: %s", event_type)
        return True
    if not settings.emails_enabled:
        return False
    if not isinstance(payload.get("email"), str):
        return False
    return deliver_welcome_email(payload=payload)
