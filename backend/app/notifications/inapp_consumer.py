import logging
import time
from typing import Any

from sqlmodel import Session

from app.core.db import engine
from app.notifications import feed_service
from app.notifications.broker import INAPP_QUEUE, RabbitConsumer

logger = logging.getLogger(__name__)
RECONNECT_INTERVAL_SECONDS = 1.0


def _handle(event_type: str, payload: dict[str, Any], message_id: str) -> bool:
    with Session(engine) as session:
        return feed_service.handle_event(
            session=session,
            event_type=event_type,
            payload=payload,
            message_id=message_id,
        )


def run() -> None:
    logger.info("In-app notification consumer started")
    while True:
        consumer: RabbitConsumer | None = None
        try:
            consumer = RabbitConsumer()
            consumer.consume(_handle, queue=INAPP_QUEUE)
        except Exception:
            logger.exception("In-app notification consumer disconnected; reconnecting")
            time.sleep(RECONNECT_INTERVAL_SECONDS)
        finally:
            if consumer is not None:
                consumer.close()


if __name__ == "__main__":
    run()
