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
        consumer.consume(lambda _event_type, _payload: True)

    callback = channel.basic_consume.call_args.kwargs["on_message_callback"]
    method = MagicMock(routing_key="user_registered", delivery_tag=42)
    callback(channel, method, MagicMock(), b'{"email":"new-user@example.com"}')
    channel.basic_ack.assert_called_once_with(delivery_tag=42)


def test_consumer_rejects_failed_delivery_for_broker_retry() -> None:
    connection = MagicMock()
    channel = connection.channel.return_value

    with patch(
        "app.notifications.broker.pika.BlockingConnection", return_value=connection
    ):
        consumer = broker.RabbitConsumer()
        consumer.consume(lambda _event_type, _payload: False)

    callback = channel.basic_consume.call_args.kwargs["on_message_callback"]
    method = MagicMock(routing_key="user_registered", delivery_tag=43)
    callback(channel, method, MagicMock(), b'{"email":"new-user@example.com"}')
    channel.basic_reject.assert_called_once_with(delivery_tag=43, requeue=True)
