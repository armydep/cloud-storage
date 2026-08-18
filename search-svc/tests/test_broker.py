from unittest.mock import MagicMock, patch

from app import broker


def test_topology_is_durable_and_has_broker_owned_delivery_limit() -> None:
    channel = MagicMock()

    broker.declare_topology(channel)

    channel.exchange_declare.assert_any_call(
        exchange=broker.NOTIFICATIONS_EXCHANGE,
        exchange_type="topic",
        durable=True,
    )
    channel.exchange_declare.assert_any_call(
        exchange=broker.SEARCH_DEAD_LETTER_EXCHANGE,
        exchange_type="topic",
        durable=True,
    )
    channel.queue_declare.assert_any_call(
        queue=broker.SEARCH_QUEUE,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-delivery-limit": broker.SEARCH_DELIVERY_LIMIT,
            "x-dead-letter-exchange": broker.SEARCH_DEAD_LETTER_EXCHANGE,
        },
    )
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


def test_search_queue_is_bound_to_file_and_folder_events() -> None:
    channel = MagicMock()

    broker.declare_topology(channel)

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


def test_consumer_acks_successful_delivery() -> None:
    connection = MagicMock()
    channel = connection.channel.return_value

    with patch("app.broker.pika.BlockingConnection", return_value=connection):
        consumer = broker.RabbitConsumer()
        consumer.consume(lambda _event_type, _payload, _message_id: True)

    callback = channel.basic_consume.call_args.kwargs["on_message_callback"]
    method = MagicMock(routing_key="file_created", delivery_tag=42)
    properties = MagicMock(message_id="outbox-id-42")
    callback(channel, method, properties, b'{"file_id":"f-1"}')
    channel.basic_ack.assert_called_once_with(delivery_tag=42)


def test_consumer_rejects_failed_delivery_for_broker_retry() -> None:
    connection = MagicMock()
    channel = connection.channel.return_value

    with patch("app.broker.pika.BlockingConnection", return_value=connection):
        consumer = broker.RabbitConsumer()
        consumer.consume(lambda _event_type, _payload, _message_id: False)

    callback = channel.basic_consume.call_args.kwargs["on_message_callback"]
    method = MagicMock(routing_key="file_created", delivery_tag=43)
    properties = MagicMock(message_id="outbox-id-43")
    callback(channel, method, properties, b'{"file_id":"f-1"}')
    channel.basic_reject.assert_called_once_with(delivery_tag=43, requeue=True)


def test_consumer_uses_search_queue_by_default() -> None:
    connection = MagicMock()
    channel = connection.channel.return_value

    with patch("app.broker.pika.BlockingConnection", return_value=connection):
        consumer = broker.RabbitConsumer()
        consumer.consume(lambda _event_type, _payload, _message_id: True)

    assert channel.basic_consume.call_args.kwargs["queue"] == broker.SEARCH_QUEUE
