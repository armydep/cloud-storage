import base64
import json
import uuid

import pytest
from sqlmodel import Session

from app.core.config import settings
from app.notifications import repository as notifications_repository
from app.notifications.events import FILE_SHARED
from app.push import consumer, service
from app.push.fcm_client import FcmSendResult, HttpV1FcmClient
from tests.utils.push import FakeFcmClient, enable_push, fake_service_account_info
from tests.utils.user import create_random_user


def test_build_fcm_client_decodes_the_credential_without_a_network_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encoded = base64.b64encode(
        json.dumps(fake_service_account_info()).encode()
    ).decode()
    monkeypatch.setattr(settings, "FCM_PROJECT_ID", "test-project")
    monkeypatch.setattr(settings, "FCM_SERVICE_ACCOUNT_JSON_BASE64", encoded)

    client = consumer.build_fcm_client()

    assert isinstance(client, HttpV1FcmClient)
    assert client._project_id == "test-project"


def test_handle_sends_push_via_a_fresh_session(db: Session) -> None:
    recipient = create_random_user(db)
    enable_push(db, recipient)

    service.register_device_token(
        session=db, user=recipient, token=uuid.uuid4().hex, platform="android"
    )
    outbox = notifications_repository.enqueue_file_shared(
        session=db,
        file_id=uuid.uuid4(),
        file_name="report.pdf",
        recipient_id=recipient.id,
        recipient_email=recipient.email,
        sharer_email="alice@example.com",
    )
    db.commit()
    fcm = FakeFcmClient()

    handled = consumer._make_handler(fcm)(FILE_SHARED, outbox.payload, str(outbox.id))

    assert handled is True
    assert len(fcm.calls) == 1
    assert "report.pdf" not in str(fcm.calls[0][1])


def test_handle_prunes_a_dead_token_via_a_fresh_session(db: Session) -> None:
    recipient = create_random_user(db)
    enable_push(db, recipient)

    service.register_device_token(
        session=db, user=recipient, token=uuid.uuid4().hex, platform="android"
    )
    outbox = notifications_repository.enqueue_file_shared(
        session=db,
        file_id=uuid.uuid4(),
        file_name="report.pdf",
        recipient_id=recipient.id,
        recipient_email=recipient.email,
        sharer_email="alice@example.com",
    )
    db.commit()
    fcm = FakeFcmClient([FcmSendResult.UNREGISTERED])

    handled = consumer._make_handler(fcm)(FILE_SHARED, outbox.payload, str(outbox.id))

    assert handled is True
