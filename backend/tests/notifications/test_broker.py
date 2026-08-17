from unittest.mock import MagicMock, patch

from app.notifications import broker


def test_topology_is_durable_and_has_broker_owned_delivery_limit() -> None:
    channel = MagicMock()

    broker.declare_topology(channel)

    channel.exchange_declare.assert_any_call(
        exchange=broker.NOTIFICATIONS_EXCHANGE,
        exchange_type="topic",
        durable=True,
    )
    channel.exchange_declare.assert_any_call(
        exchange=broker.DEAD_LETTER_EXCHANGE,
        exchange_type="topic",
        durable=True,
    )
    channel.queue_declare.assert_any_call(
        queue=broker.EMAIL_QUEUE,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-delivery-limit": broker.EMAIL_DELIVERY_LIMIT,
            "x-dead-letter-exchange": broker.DEAD_LETTER_EXCHANGE,
        },
    )
    channel.queue_declare.assert_any_call(
        queue=broker.EMAIL_DEAD_LETTER_QUEUE,
        durable=True,
        arguments={"x-queue-type": "quorum"},
    )


def test_email_queue_is_bound_to_user_registered_and_file_shared() -> None:
    channel = MagicMock()

    broker.declare_topology(channel)

    channel.queue_bind.assert_any_call(
        queue=broker.EMAIL_QUEUE,
        exchange=broker.NOTIFICATIONS_EXCHANGE,
        routing_key="user_registered",
    )
    channel.queue_bind.assert_any_call(
        queue=broker.EMAIL_QUEUE,
        exchange=broker.NOTIFICATIONS_EXCHANGE,
        routing_key=broker.FILE_SHARED_ROUTING_KEY,
    )


def test_inapp_queue_is_durable_and_bound_only_to_file_shared() -> None:
    channel = MagicMock()

    broker.declare_topology(channel)

    channel.queue_declare.assert_any_call(
        queue=broker.INAPP_QUEUE,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-delivery-limit": broker.INAPP_DELIVERY_LIMIT,
            "x-dead-letter-exchange": broker.INAPP_DEAD_LETTER_EXCHANGE,
        },
    )
    channel.queue_bind.assert_any_call(
        queue=broker.INAPP_QUEUE,
        exchange=broker.NOTIFICATIONS_EXCHANGE,
        routing_key=broker.FILE_SHARED_ROUTING_KEY,
    )
    bound_routing_keys = [
        call.kwargs["routing_key"]
        for call in channel.queue_bind.call_args_list
        if call.kwargs.get("queue") == broker.INAPP_QUEUE
    ]
    assert bound_routing_keys == [broker.FILE_SHARED_ROUTING_KEY]

    channel.queue_declare.assert_any_call(
        queue=broker.INAPP_DEAD_LETTER_QUEUE,
        durable=True,
        arguments={"x-queue-type": "quorum"},
    )
    channel.queue_bind.assert_any_call(
        queue=broker.INAPP_DEAD_LETTER_QUEUE,
        exchange=broker.INAPP_DEAD_LETTER_EXCHANGE,
        routing_key="#",
    )


def test_search_queue_is_durable_and_bound_to_file_and_folder_events() -> None:
    channel = MagicMock()

    broker.declare_topology(channel)

    channel.queue_declare.assert_any_call(
        queue=broker.SEARCH_QUEUE,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-delivery-limit": broker.SEARCH_DELIVERY_LIMIT,
            "x-dead-letter-exchange": broker.SEARCH_DEAD_LETTER_EXCHANGE,
        },
    )
    bound_routing_keys = [
        call.kwargs["routing_key"]
        for call in channel.queue_bind.call_args_list
        if call.kwargs.get("queue") == broker.SEARCH_QUEUE
    ]
    assert bound_routing_keys == [
        broker.FILE_CREATED_ROUTING_KEY,
        broker.FILE_DELETED_ROUTING_KEY,
        broker.FOLDER_DELETED_ROUTING_KEY,
    ]

    channel.queue_declare.assert_any_call(
        queue=broker.SEARCH_DEAD_LETTER_QUEUE,
        durable=True,
        arguments={"x-queue-type": "quorum"},
    )
    channel.queue_bind.assert_any_call(
        queue=broker.SEARCH_DEAD_LETTER_QUEUE,
        exchange=broker.SEARCH_DEAD_LETTER_EXCHANGE,
        routing_key="#",
    )


def test_publisher_enables_confirms_and_publishes_persistent_message() -> None:
    connection = MagicMock()
    channel = connection.channel.return_value

    with patch(
        "app.notifications.broker.pika.BlockingConnection", return_value=connection
    ):
        publisher = broker.RabbitPublisher()
        publisher.publish(
            event_type="user_registered",
            payload={"email": "new-user@example.com"},
            message_id="event-id",
        )

    channel.confirm_delivery.assert_called_once_with()
    publish_call = channel.basic_publish.call_args
    assert publish_call.kwargs["exchange"] == broker.NOTIFICATIONS_EXCHANGE
    assert publish_call.kwargs["routing_key"] == "user_registered"
    assert publish_call.kwargs["mandatory"] is True
    assert publish_call.kwargs["properties"].delivery_mode == 2


def test_consumer_acks_successful_delivery() -> None:
    connection = MagicMock()
    channel = connection.channel.return_value

    with patch(
        "app.notifications.broker.pika.BlockingConnection", return_value=connection
    ):
        consumer = broker.RabbitConsumer()
        consumer.consume(lambda _event_type, _payload, _message_id: True)

    callback = channel.basic_consume.call_args.kwargs["on_message_callback"]
    method = MagicMock(routing_key="user_registered", delivery_tag=42)
    properties = MagicMock(message_id="outbox-id-42")
    callback(channel, method, properties, b'{"email":"new-user@example.com"}')
    channel.basic_ack.assert_called_once_with(delivery_tag=42)


def test_consumer_passes_message_id_to_handler() -> None:
    connection = MagicMock()
    channel = connection.channel.return_value
    received: dict[str, object] = {}

    def handler(event_type: str, payload: dict[str, object], message_id: str) -> bool:
        received["event_type"] = event_type
        received["payload"] = payload
        received["message_id"] = message_id
        return True

    with patch(
        "app.notifications.broker.pika.BlockingConnection", return_value=connection
    ):
        consumer = broker.RabbitConsumer()
        consumer.consume(handler, queue=broker.INAPP_QUEUE)

    channel.basic_consume.assert_called_once()
    assert channel.basic_consume.call_args.kwargs["queue"] == broker.INAPP_QUEUE
    callback = channel.basic_consume.call_args.kwargs["on_message_callback"]
    method = MagicMock(routing_key="file_shared", delivery_tag=7)
    properties = MagicMock(message_id="outbox-id-7")
    callback(channel, method, properties, b'{"file_name":"report.pdf"}')

    assert received == {
        "event_type": "file_shared",
        "payload": {"file_name": "report.pdf"},
        "message_id": "outbox-id-7",
    }


def test_consumer_rejects_failed_delivery_for_broker_retry() -> None:
    connection = MagicMock()
    channel = connection.channel.return_value

    with patch(
        "app.notifications.broker.pika.BlockingConnection", return_value=connection
    ):
        consumer = broker.RabbitConsumer()
        consumer.consume(lambda _event_type, _payload, _message_id: False)

    callback = channel.basic_consume.call_args.kwargs["on_message_callback"]
    method = MagicMock(routing_key="user_registered", delivery_tag=43)
    properties = MagicMock(message_id="outbox-id-43")
    callback(channel, method, properties, b'{"email":"new-user@example.com"}')
    channel.basic_reject.assert_called_once_with(delivery_tag=43, requeue=True)
