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

INAPP_QUEUE = "q.inapp"
INAPP_DEAD_LETTER_EXCHANGE = "notifications.dead-letter.inapp"
INAPP_DEAD_LETTER_QUEUE = "q.inapp.dead-letter"
INAPP_DELIVERY_LIMIT = 5

# Consumed by search-svc, a separate deployable (Phase 10) that keeps its own
# copy of these names rather than importing this module -- see
# docs/phases/phase-10-search-service.md decision 1 and constraint 3 there.
# Declared here anyway, even though backend never consumes it, so the queue
# and its bindings exist before search-svc's indexer has ever started; a
# topic exchange silently discards a message that matches no binding.
SEARCH_QUEUE = "q.search"
SEARCH_DEAD_LETTER_EXCHANGE = "notifications.dead-letter.search"
SEARCH_DEAD_LETTER_QUEUE = "q.search.dead-letter"
SEARCH_DELIVERY_LIMIT = 5

FILE_SHARED_ROUTING_KEY = "file_shared"
FILE_CREATED_ROUTING_KEY = "file_created"
FILE_DELETED_ROUTING_KEY = "file_deleted"
FOLDER_DELETED_ROUTING_KEY = "folder_deleted"


class EventPublisher(Protocol):
    def publish(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        message_id: str,
    ) -> None: ...


# (routing_key, payload, message_id) -> handled. message_id is the outbox
# row's id, set by RabbitPublisher.publish; consumers that need idempotency
# (the in-app feed) use it against notifications.outbox_id UNIQUE.
EventHandler = Callable[[str, dict[str, Any], str], bool]


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
    channel.queue_bind(
        queue=EMAIL_QUEUE,
        exchange=NOTIFICATIONS_EXCHANGE,
        routing_key=FILE_SHARED_ROUTING_KEY,
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

    # In-app feed channel, added in Phase 9. `user_registered` is deliberately
    # not bound here (decision 8) -- only events useful after the fact belong
    # in the feed.
    channel.exchange_declare(
        exchange=INAPP_DEAD_LETTER_EXCHANGE,
        exchange_type="topic",
        durable=True,
    )
    channel.queue_declare(
        queue=INAPP_QUEUE,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-delivery-limit": INAPP_DELIVERY_LIMIT,
            "x-dead-letter-exchange": INAPP_DEAD_LETTER_EXCHANGE,
        },
    )
    channel.queue_bind(
        queue=INAPP_QUEUE,
        exchange=NOTIFICATIONS_EXCHANGE,
        routing_key=FILE_SHARED_ROUTING_KEY,
    )
    channel.queue_declare(
        queue=INAPP_DEAD_LETTER_QUEUE,
        durable=True,
        arguments={"x-queue-type": "quorum"},
    )
    channel.queue_bind(
        queue=INAPP_DEAD_LETTER_QUEUE,
        exchange=INAPP_DEAD_LETTER_EXCHANGE,
        routing_key="#",
    )

    # search-svc's indexer channel, added in Phase 10. No rename events are
    # bound yet -- file_renamed/folder_renamed cannot be emitted because the
    # backend has no rename route yet (ROADMAP 1.2, 1.3).
    channel.exchange_declare(
        exchange=SEARCH_DEAD_LETTER_EXCHANGE,
        exchange_type="topic",
        durable=True,
    )
    channel.queue_declare(
        queue=SEARCH_QUEUE,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-delivery-limit": SEARCH_DELIVERY_LIMIT,
            "x-dead-letter-exchange": SEARCH_DEAD_LETTER_EXCHANGE,
        },
    )
    channel.queue_bind(
        queue=SEARCH_QUEUE,
        exchange=NOTIFICATIONS_EXCHANGE,
        routing_key=FILE_CREATED_ROUTING_KEY,
    )
    channel.queue_bind(
        queue=SEARCH_QUEUE,
        exchange=NOTIFICATIONS_EXCHANGE,
        routing_key=FILE_DELETED_ROUTING_KEY,
    )
    channel.queue_bind(
        queue=SEARCH_QUEUE,
        exchange=NOTIFICATIONS_EXCHANGE,
        routing_key=FOLDER_DELETED_ROUTING_KEY,
    )
    channel.queue_declare(
        queue=SEARCH_DEAD_LETTER_QUEUE,
        durable=True,
        arguments={"x-queue-type": "quorum"},
    )
    channel.queue_bind(
        queue=SEARCH_DEAD_LETTER_QUEUE,
        exchange=SEARCH_DEAD_LETTER_EXCHANGE,
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

    def consume(self, handler: EventHandler, *, queue: str = EMAIL_QUEUE) -> None:
        def on_message(
            channel: BlockingChannel,
            method: pika.spec.Basic.Deliver,
            properties: pika.BasicProperties,
            body: bytes,
        ) -> None:
            try:
                payload = cast(dict[str, Any], json.loads(body))
                message_id = properties.message_id or ""
                handled = handler(str(method.routing_key), payload, message_id)
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
            queue=queue,
            on_message_callback=on_message,
            auto_ack=False,
        )
        self._channel.start_consuming()

    def close(self) -> None:
        if self._connection.is_open:
            self._connection.close()
