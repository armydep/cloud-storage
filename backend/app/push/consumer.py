import base64
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.notifications.broker import PUSH_QUEUE, RabbitConsumer
from app.push import service
from app.push.fcm_client import FcmClient, GoogleAuthTokenProvider, HttpV1FcmClient

logger = logging.getLogger(__name__)
RECONNECT_INTERVAL_SECONDS = 1.0


def build_fcm_client() -> FcmClient:
    assert settings.FCM_PROJECT_ID is not None
    assert settings.FCM_SERVICE_ACCOUNT_JSON_BASE64 is not None
    service_account_info = json.loads(
        base64.b64decode(settings.FCM_SERVICE_ACCOUNT_JSON_BASE64)
    )
    token_provider = GoogleAuthTokenProvider(service_account_info)
    return HttpV1FcmClient(
        project_id=settings.FCM_PROJECT_ID, token_provider=token_provider
    )


def _make_handler(
    fcm_client: FcmClient,
) -> Callable[[str, dict[str, Any], str], bool]:
    def _handle(event_type: str, payload: dict[str, Any], message_id: str) -> bool:
        with Session(engine) as session:
            return service.handle_event(
                session=session,
                fcm_client=fcm_client,
                event_type=event_type,
                payload=payload,
                message_id=message_id,
            )

    return _handle


def run() -> None:
    logger.info("Push notification consumer started")
    while True:
        if not settings.fcm_configured:
            logger.warning("FCM is not configured; push consumer is waiting")
            time.sleep(RECONNECT_INTERVAL_SECONDS)
            continue

        consumer: RabbitConsumer | None = None
        try:
            fcm_client = build_fcm_client()
            consumer = RabbitConsumer()
            consumer.consume(_make_handler(fcm_client), queue=PUSH_QUEUE)
        except Exception:
            logger.exception("Push notification consumer disconnected; reconnecting")
            time.sleep(RECONNECT_INTERVAL_SECONDS)
        finally:
            if consumer is not None:
                consumer.close()


if __name__ == "__main__":
    run()
