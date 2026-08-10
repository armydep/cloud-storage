import logging
import time

from sqlmodel import Session

from app.core.db import engine
from app.notifications.service import process_next

logger = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 1.0


def run() -> None:
    logger.info("Notification worker started")
    while True:
        try:
            with Session(engine) as session:
                processed = process_next(session=session)
        except Exception:
            logger.exception("Notification delivery failed; row remains unpublished")
            processed = False
        if not processed:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
