import logging
import time

from sqlmodel import Session

from app.core.db import engine
from app.models import get_datetime_utc
from app.notifications import repository
from app.notifications.broker import EventPublisher, RabbitPublisher

logger = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 1.0


def process_next(*, session: Session, publisher: EventPublisher) -> bool:
    notification = repository.claim_next_unpublished(session=session)
    if notification is None:
        return False

    publisher.publish(
        event_type=notification.event_type,
        payload=notification.payload,
        message_id=str(notification.id),
    )
    notification.published_at = get_datetime_utc()
    session.add(notification)
    session.commit()
    return True


def run() -> None:
    logger.info("Notification relay started")
    while True:
        publisher: RabbitPublisher | None = None
        try:
            publisher = RabbitPublisher()
            while True:
                with Session(engine) as session:
                    processed = process_next(session=session, publisher=publisher)
                if not processed:
                    time.sleep(POLL_INTERVAL_SECONDS)
        except Exception:
            logger.exception("Notification publish failed; row remains unpublished")
            time.sleep(POLL_INTERVAL_SECONDS)
        finally:
            if publisher is not None:
                publisher.close()


if __name__ == "__main__":
    run()
