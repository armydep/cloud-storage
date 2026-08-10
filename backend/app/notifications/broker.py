import json
import logging
from collections.abc import Callable
from typing import Any, Protocol, cast

import pika  # type: ignore[import-untyped]
from pika.adapters.blocking_connection import (  # type: ignore[import-untyped]
    BlockingChannel,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

NOTIFICATIONS_EXCHANGE = "notifications"
EMAIL_QUEUE = "q.email"
DEAD_LETTER_EXCHANGE = "notifications.dead-letter"
EMAIL_DEAD_LETTER_QUEUE = "q.email.dead-letter"
EMAIL_DELIVERY_LIMIT = 5


class EventPublisher(Protocol):
    def publish(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        message_id: str,
    ) -> None: ...


EventHandler = Callable[[str, dict[str, Any]], bool]


def _connection_parameters() -> pika.ConnectionParameters:
    return pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        credentials=pika.PlainCredentials(
            settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD
        ),
        heartbeat=60,
        blocked_connection_timeout=30,
    )


def declare_topology(channel: BlockingChannel) -> None:
    channel.exchange_declare(
        exchange=NOTIFICATIONS_EXCHANGE,
        exchange_type="topic",
        durable=True,
    )
    channel.exchange_declare(
        exchange=DEAD_LETTER_EXCHANGE,
        exchange_type="topic",
        durable=True,
    )
    channel.queue_declare(
        queue=EMAIL_QUEUE,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-delivery-limit": EMAIL_DELIVERY_LIMIT,
            "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
        },
    )
    channel.queue_bind(
        queue=EMAIL_QUEUE,
        exchange=NOTIFICATIONS_EXCHANGE,
        routing_key="user_registered",
    )
    channel.queue_declare(
        queue=EMAIL_DEAD_LETTER_QUEUE,
        durable=True,
        arguments={"x-queue-type": "quorum"},
    )
    channel.queue_bind(
        queue=EMAIL_DEAD_LETTER_QUEUE,
        exchange=DEAD_LETTER_EXCHANGE,
        routing_key="#",
    )


class RabbitPublisher:
    def __init__(self) -> None:
        self._connection = pika.BlockingConnection(_connection_parameters())
        self._channel = self._connection.channel()
        declare_topology(self._channel)
        self._channel.confirm_delivery()

    def publish(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        message_id: str,
    ) -> None:
        self._channel.basic_publish(
            exchange=NOTIFICATIONS_EXCHANGE,
            routing_key=event_type,
            body=json.dumps(payload).encode(),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                message_id=message_id,
            ),
            mandatory=True,
        )

    def close(self) -> None:
        if self._connection.is_open:
            self._connection.close()


class RabbitConsumer:
    def __init__(self) -> None:
        self._connection = pika.BlockingConnection(_connection_parameters())
        self._channel = self._connection.channel()
        declare_topology(self._channel)
        self._channel.basic_qos(prefetch_count=1)

    def consume(self, handler: EventHandler) -> None:
        def on_message(
            channel: BlockingChannel,
            method: pika.spec.Basic.Deliver,
            _properties: pika.BasicProperties,
            body: bytes,
        ) -> None:
            try:
                payload = cast(dict[str, Any], json.loads(body))
                handled = handler(str(method.routing_key), payload)
            except Exception:
                logger.exception("Notification delivery failed; message will retry")
                handled = False

            if handled:
                channel.basic_ack(delivery_tag=method.delivery_tag)
            else:
                # RabbitMQ 4.3 counts AMQP basic.reject as a failed delivery for
                # quorum queue delivery limits. basic.nack requeues without
                # incrementing that counter and can loop forever.
                channel.basic_reject(delivery_tag=method.delivery_tag, requeue=True)

        self._channel.basic_consume(
            queue=EMAIL_QUEUE,
            on_message_callback=on_message,
            auto_ack=False,
        )
        self._channel.start_consuming()

    def close(self) -> None:
        if self._connection.is_open:
            self._connection.close()
