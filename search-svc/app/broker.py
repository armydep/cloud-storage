import json
import logging
from collections.abc import Callable
from typing import Any, cast

import pika  # type: ignore[import-untyped]
from pika.adapters.blocking_connection import (  # type: ignore[import-untyped]
    BlockingChannel,
)

from app.config import settings

logger = logging.getLogger(__name__)

# These names -- and the queue arguments used to declare them below -- are a
# contract with the backend, not a shared import. backend's own
# app/notifications/broker.py declares the same queue with the same
# arguments; a mismatch between the two would make RabbitMQ reject one side's
# declaration with PRECONDITION_FAILED. See
# docs/phases/phase-10-search-service.md decision 1 and constraint 3.
NOTIFICATIONS_EXCHANGE = "notifications"
SEARCH_QUEUE = "q.search"
SEARCH_DEAD_LETTER_EXCHANGE = "notifications.dead-letter.search"
SEARCH_DEAD_LETTER_QUEUE = "q.search.dead-letter"
SEARCH_DELIVERY_LIMIT = 5

FILE_CREATED_ROUTING_KEY = "file_created"
FILE_DELETED_ROUTING_KEY = "file_deleted"
FOLDER_DELETED_ROUTING_KEY = "folder_deleted"


# (routing_key, payload, message_id) -> handled. Mirrors backend's
# EventHandler shape; message_id is unused by the indexer today (indexing is
# idempotent by document id already) but kept in the signature so a future
# handler can use it without a breaking change.
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
    """Declare only the pieces search-svc's indexer touches.

    backend declares the full notifications topology, including this queue,
    so it exists even if this process has never started (see backend's
    declare_topology docstring). Declaring it again here is idempotent and
    keeps this consumer self-sufficient if it ever starts first.
    """
    channel.exchange_declare(
        exchange=NOTIFICATIONS_EXCHANGE,
        exchange_type="topic",
        durable=True,
    )
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


class RabbitConsumer:
    def __init__(self) -> None:
        self._connection = pika.BlockingConnection(_connection_parameters())
        self._channel = self._connection.channel()
        declare_topology(self._channel)
        self._channel.basic_qos(prefetch_count=1)

    def consume(self, handler: EventHandler, *, queue: str = SEARCH_QUEUE) -> None:
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
                logger.exception("Indexing failed; message will retry")
                handled = False

            if handled:
                channel.basic_ack(delivery_tag=method.delivery_tag)
            else:
                # RabbitMQ 4.3 counts AMQP basic.reject as a failed delivery
                # for quorum queue delivery limits. basic.nack requeues
                # without incrementing that counter and can loop forever.
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
