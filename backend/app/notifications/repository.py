from sqlmodel import Session, col, select

from app.models import User
from app.notifications.models import NotificationOutbox

USER_REGISTERED = "user_registered"


def enqueue_user_registered(*, session: Session, user: User) -> NotificationOutbox:
    notification = NotificationOutbox(
        event_type=USER_REGISTERED,
        payload={"user_id": str(user.id), "email": user.email},
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
