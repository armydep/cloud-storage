import logging
import time

from app.core.config import settings
from app.notifications import service
from app.notifications.broker import RabbitConsumer

logger = logging.getLogger(__name__)
RECONNECT_INTERVAL_SECONDS = 1.0


def run() -> None:
    logger.info("Email notification consumer started")
    while True:
        if not settings.emails_enabled:
            logger.warning("Email delivery is disabled; consumer is waiting")
            time.sleep(RECONNECT_INTERVAL_SECONDS)
            continue

        consumer: RabbitConsumer | None = None
        try:
            consumer = RabbitConsumer()
            consumer.consume(service.handle_event)
        except Exception:
            logger.exception("Notification consumer disconnected; reconnecting")
            time.sleep(RECONNECT_INTERVAL_SECONDS)
        finally:
            if consumer is not None:
                consumer.close()


if __name__ == "__main__":
    run()
