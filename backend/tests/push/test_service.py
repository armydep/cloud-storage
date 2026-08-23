import uuid
from typing import Any

from sqlmodel import Session, select

from app.notifications.events import FILE_SHARED
from app.push import service
from app.push.fcm_client import FcmSendResult
from app.push.models import DeviceToken
from tests.utils.push import FakeFcmClient
from tests.utils.push import enable_push as _enable_push
from tests.utils.user import create_random_user


def _shared_payload(
    *, recipient_id: uuid.UUID, file_id: uuid.UUID | None = None
) -> dict[str, Any]:
    return {
        "file_id": str(file_id or uuid.uuid4()),
        "file_name": "report.pdf",
        "recipient_id": str(recipient_id),
        "recipient_email": "recipient@example.com",
        "sharer_email": "sharer@example.com",
    }


def test_handle_event_does_nothing_when_push_is_disabled(db: Session) -> None:
    user = create_random_user(db)
    service.register_device_token(
        session=db, user=user, token=uuid.uuid4().hex, platform="android"
    )
    fcm = FakeFcmClient()

    handled = service.handle_event(
        session=db,
        fcm_client=fcm,
        event_type=FILE_SHARED,
        payload=_shared_payload(recipient_id=user.id),
        message_id=str(uuid.uuid4()),
    )

    assert handled is True
    assert fcm.calls == []


def test_handle_event_is_a_noop_with_no_registered_devices(db: Session) -> None:
    user = create_random_user(db)
    _enable_push(db, user)
    fcm = FakeFcmClient()

    handled = service.handle_event(
        session=db,
        fcm_client=fcm,
        event_type=FILE_SHARED,
        payload=_shared_payload(recipient_id=user.id),
        message_id=str(uuid.uuid4()),
    )

    assert handled is True
    assert fcm.calls == []


def test_handle_event_sends_to_every_token_the_user_holds(db: Session) -> None:
    user = create_random_user(db)
    _enable_push(db, user)
    token_a, token_b = uuid.uuid4().hex, uuid.uuid4().hex
    service.register_device_token(
        session=db, user=user, token=token_a, platform="android"
    )
    service.register_device_token(
        session=db, user=user, token=token_b, platform="android"
    )
    fcm = FakeFcmClient()
    message_id = str(uuid.uuid4())
    file_id = uuid.uuid4()

    handled = service.handle_event(
        session=db,
        fcm_client=fcm,
        event_type=FILE_SHARED,
        payload=_shared_payload(recipient_id=user.id, file_id=file_id),
        message_id=message_id,
    )

    assert handled is True
    sent_tokens = {token for token, _ in fcm.calls}
    assert sent_tokens == {token_a, token_b}
    for _, data in fcm.calls:
        assert data == {
            "event_type": FILE_SHARED,
            "file_id": str(file_id),
            "notification_id": message_id,
            "title": service.GENERIC_TITLE,
        }


def test_handle_event_payload_never_contains_the_file_name(db: Session) -> None:
    """Verified against the wire (the FcmClient.send data argument), not the

    rendered notification -- decision 12 exists specifically to keep file
    names off Google's infrastructure.
    """
    user = create_random_user(db)
    _enable_push(db, user)
    service.register_device_token(
        session=db, user=user, token=uuid.uuid4().hex, platform="android"
    )
    fcm = FakeFcmClient()

    service.handle_event(
        session=db,
        fcm_client=fcm,
        event_type=FILE_SHARED,
        payload=_shared_payload(recipient_id=user.id),
        message_id=str(uuid.uuid4()),
    )

    assert len(fcm.calls) == 1
    _, data = fcm.calls[0]
    assert "report.pdf" not in str(data)
    assert "file_name" not in data
    assert "sharer_email" not in data
    assert "recipient_email" not in data


def test_handle_event_one_dead_token_does_not_abort_the_others(db: Session) -> None:
    user = create_random_user(db)
    _enable_push(db, user)
    dead_token, live_token = uuid.uuid4().hex, uuid.uuid4().hex
    service.register_device_token(
        session=db, user=user, token=dead_token, platform="android"
    )
    service.register_device_token(
        session=db, user=user, token=live_token, platform="android"
    )
    fcm = FakeFcmClient([FcmSendResult.UNREGISTERED, FcmSendResult.SUCCESS])

    handled = service.handle_event(
        session=db,
        fcm_client=fcm,
        event_type=FILE_SHARED,
        payload=_shared_payload(recipient_id=user.id),
        message_id=str(uuid.uuid4()),
    )

    assert handled is True
    assert len(fcm.calls) == 2
    remaining = db.exec(select(DeviceToken).where(DeviceToken.user_id == user.id)).all()
    assert [t.token for t in remaining] == [live_token]


def test_handle_event_prunes_not_found_token(db: Session) -> None:
    user = create_random_user(db)
    _enable_push(db, user)
    token = uuid.uuid4().hex
    service.register_device_token(
        session=db, user=user, token=token, platform="android"
    )
    fcm = FakeFcmClient([FcmSendResult.NOT_FOUND])

    handled = service.handle_event(
        session=db,
        fcm_client=fcm,
        event_type=FILE_SHARED,
        payload=_shared_payload(recipient_id=user.id),
        message_id=str(uuid.uuid4()),
    )

    assert handled is True
    assert (
        db.exec(select(DeviceToken).where(DeviceToken.token == token)).first() is None
    )


def test_handle_event_a_pruned_token_is_not_retried_on_the_next_share(
    db: Session,
) -> None:
    user = create_random_user(db)
    _enable_push(db, user)
    token = uuid.uuid4().hex
    service.register_device_token(
        session=db, user=user, token=token, platform="android"
    )
    fcm = FakeFcmClient([FcmSendResult.UNREGISTERED])
    service.handle_event(
        session=db,
        fcm_client=fcm,
        event_type=FILE_SHARED,
        payload=_shared_payload(recipient_id=user.id),
        message_id=str(uuid.uuid4()),
    )

    handled = service.handle_event(
        session=db,
        fcm_client=fcm,
        event_type=FILE_SHARED,
        payload=_shared_payload(recipient_id=user.id),
        message_id=str(uuid.uuid4()),
    )

    assert handled is True
    # Only the first share's send was attempted -- the second share found no
    # remaining tokens for this user and never called the client again.
    assert len(fcm.calls) == 1


def test_handle_event_a_transient_failure_causes_a_retry_of_the_whole_message(
    db: Session,
) -> None:
    user = create_random_user(db)
    _enable_push(db, user)
    service.register_device_token(
        session=db, user=user, token=uuid.uuid4().hex, platform="android"
    )
    fcm = FakeFcmClient([FcmSendResult.OTHER_ERROR])

    handled = service.handle_event(
        session=db,
        fcm_client=fcm,
        event_type=FILE_SHARED,
        payload=_shared_payload(recipient_id=user.id),
        message_id=str(uuid.uuid4()),
    )

    assert handled is False


def test_handle_event_duplicate_delivery_carries_the_same_notification_id(
    db: Session,
) -> None:
    """Delivery is at-least-once (decision 7 / phase 8 decision 5): the same

    outbox message can be redelivered. The client de-duplicates on
    `notification_id`, so this asserts the consumer sends the *same* value
    for `message_id` across redeliveries rather than trying to dedupe itself.
    """
    user = create_random_user(db)
    _enable_push(db, user)
    service.register_device_token(
        session=db, user=user, token=uuid.uuid4().hex, platform="android"
    )
    fcm = FakeFcmClient()
    message_id = str(uuid.uuid4())
    payload = _shared_payload(recipient_id=user.id)

    service.handle_event(
        session=db,
        fcm_client=fcm,
        event_type=FILE_SHARED,
        payload=payload,
        message_id=message_id,
    )
    service.handle_event(
        session=db,
        fcm_client=fcm,
        event_type=FILE_SHARED,
        payload=payload,
        message_id=message_id,
    )

    assert fcm.calls[0][1]["notification_id"] == message_id
    assert fcm.calls[1][1]["notification_id"] == message_id


def test_handle_event_ignores_unsupported_event_types(db: Session) -> None:
    user = create_random_user(db)
    _enable_push(db, user)
    fcm = FakeFcmClient()

    handled = service.handle_event(
        session=db,
        fcm_client=fcm,
        event_type="user_registered",
        payload={},
        message_id=str(uuid.uuid4()),
    )

    assert handled is True
    assert fcm.calls == []


def test_handle_event_rejects_a_recipient_id_that_is_not_a_uuid(db: Session) -> None:
    fcm = FakeFcmClient()
    payload = _shared_payload(recipient_id=uuid.uuid4())
    payload["recipient_id"] = "not-a-uuid"

    handled = service.handle_event(
        session=db,
        fcm_client=fcm,
        event_type=FILE_SHARED,
        payload=payload,
        message_id=str(uuid.uuid4()),
    )

    assert handled is False
    assert fcm.calls == []


def test_handle_event_a_raised_exception_from_the_fcm_client_is_treated_as_transient(
    db: Session,
) -> None:
    user = create_random_user(db)
    _enable_push(db, user)
    service.register_device_token(
        session=db, user=user, token=uuid.uuid4().hex, platform="android"
    )

    class RaisingFcmClient:
        def send(self, *, token: str, data: dict[str, str]) -> FcmSendResult:
            raise RuntimeError("boom")

    handled = service.handle_event(
        session=db,
        fcm_client=RaisingFcmClient(),
        event_type=FILE_SHARED,
        payload=_shared_payload(recipient_id=user.id),
        message_id=str(uuid.uuid4()),
    )

    assert handled is False


def test_handle_event_rejects_malformed_payload(db: Session) -> None:
    fcm = FakeFcmClient()

    handled = service.handle_event(
        session=db,
        fcm_client=fcm,
        event_type=FILE_SHARED,
        payload={"file_id": "not-a-uuid-holder"},
        message_id=str(uuid.uuid4()),
    )

    assert handled is False
    assert fcm.calls == []


def test_register_device_token_returns_the_public_shape(db: Session) -> None:
    user = create_random_user(db)
    token = uuid.uuid4().hex

    result = service.register_device_token(
        session=db, user=user, token=token, platform="android"
    )

    assert result.token == token
    assert result.platform == "android"
    assert result.created_at is not None
    assert result.last_seen_at is not None


def test_unregister_device_token_deletes_the_row(db: Session) -> None:
    user = create_random_user(db)
    token = uuid.uuid4().hex
    service.register_device_token(
        session=db, user=user, token=token, platform="android"
    )

    service.unregister_device_token(session=db, user=user, token=token)

    assert (
        db.exec(select(DeviceToken).where(DeviceToken.token == token)).first() is None
    )
