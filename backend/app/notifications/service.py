from typing import cast

from sqlmodel import Session

from app.core.config import settings
from app.models import get_datetime_utc
from app.notifications import repository
from app.notifications.models import NotificationOutbox
from app.utils import EmailData, render_email_template, send_email


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


def deliver(notification: NotificationOutbox) -> None:
    if notification.event_type != repository.USER_REGISTERED:
        raise ValueError(f"Unsupported notification event: {notification.event_type}")
    email_to = cast(str, notification.payload["email"])
    email = generate_welcome_email(email_to=email_to)
    sent = send_email(
        email_to=email_to,
        subject=email.subject,
        html_content=email.html_content,
    )
    if not sent:
        raise RuntimeError("Email delivery failed")


def process_next(*, session: Session) -> bool:
    if not settings.emails_enabled:
        return False

    notification = repository.claim_next_unpublished(session=session)
    if notification is None:
        return False

    deliver(notification)
    notification.published_at = get_datetime_utc()
    session.add(notification)
    session.commit()
    return True
