import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.models import UserCreate
from app.push.models import DeviceToken
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


def test_register_device_token(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    token = uuid.uuid4().hex

    r = client.post(
        f"{settings.API_V1_STR}/push/device-tokens",
        headers=normal_user_token_headers,
        json={"token": token, "platform": "android"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["token"] == token
    assert body["platform"] == "android"
    assert db.exec(select(DeviceToken).where(DeviceToken.token == token)).first()


def test_register_device_token_requires_authentication(client: TestClient) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/push/device-tokens",
        json={"token": uuid.uuid4().hex, "platform": "android"},
    )

    assert r.status_code == 401


def test_register_device_token_rejects_an_invalid_platform(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/push/device-tokens",
        headers=normal_user_token_headers,
        json={"token": uuid.uuid4().hex, "platform": "ios"},
    )

    assert r.status_code == 422


def test_register_device_token_moves_between_users(
    client: TestClient, db: Session
) -> None:
    """The same token registering under a different user moves the row --

    the acceptance criterion this endpoint exists to satisfy, exercised
    through the API rather than the repository directly.
    """
    first_email, second_email = random_email(), random_email()
    password = random_lower_string()
    crud.create_user(
        session=db, user_create=UserCreate(email=first_email, password=password)
    )
    crud.create_user(
        session=db, user_create=UserCreate(email=second_email, password=password)
    )
    first_headers = user_authentication_headers(
        client=client, email=first_email, password=password
    )
    second_headers = user_authentication_headers(
        client=client, email=second_email, password=password
    )
    token = uuid.uuid4().hex

    client.post(
        f"{settings.API_V1_STR}/push/device-tokens",
        headers=first_headers,
        json={"token": token, "platform": "android"},
    )
    r = client.post(
        f"{settings.API_V1_STR}/push/device-tokens",
        headers=second_headers,
        json={"token": token, "platform": "android"},
    )

    assert r.status_code == 200
    rows = db.exec(select(DeviceToken).where(DeviceToken.token == token)).all()
    assert len(rows) == 1

    second_user_id = client.get(
        f"{settings.API_V1_STR}/users/me", headers=second_headers
    ).json()["id"]
    assert str(rows[0].user_id) == second_user_id


def test_unregister_device_token(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    token = uuid.uuid4().hex
    client.post(
        f"{settings.API_V1_STR}/push/device-tokens",
        headers=normal_user_token_headers,
        json={"token": token, "platform": "android"},
    )

    r = client.delete(
        f"{settings.API_V1_STR}/push/device-tokens/{token}",
        headers=normal_user_token_headers,
    )

    assert r.status_code == 204
    assert (
        db.exec(select(DeviceToken).where(DeviceToken.token == token)).first() is None
    )


def test_unregister_device_token_is_a_noop_when_missing(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.delete(
        f"{settings.API_V1_STR}/push/device-tokens/never-registered",
        headers=normal_user_token_headers,
    )

    assert r.status_code == 204


def test_unregister_device_token_requires_authentication(client: TestClient) -> None:
    r = client.delete(f"{settings.API_V1_STR}/push/device-tokens/some-token")

    assert r.status_code == 401


def test_signing_out_unregisters_the_token_so_the_next_user_does_not_inherit_it(
    client: TestClient, db: Session
) -> None:
    """Unregistering on logout is a security requirement, not hygiene

    (design doc decision 6): if the token survives, the next person to sign
    in on the same device would receive the previous user's notifications.
    This test is the mobile client's contract with the backend -- the app
    is expected to call the unregister endpoint before clearing its local
    session, exercised here directly against the API.
    """
    first_email, second_email = random_email(), random_email()
    password = random_lower_string()
    crud.create_user(
        session=db, user_create=UserCreate(email=first_email, password=password)
    )
    crud.create_user(
        session=db, user_create=UserCreate(email=second_email, password=password)
    )
    first_headers = user_authentication_headers(
        client=client, email=first_email, password=password
    )
    second_headers = user_authentication_headers(
        client=client, email=second_email, password=password
    )
    token = uuid.uuid4().hex
    client.post(
        f"{settings.API_V1_STR}/push/device-tokens",
        headers=first_headers,
        json={"token": token, "platform": "android"},
    )

    # The first user signs out -- the app unregisters their token.
    client.delete(
        f"{settings.API_V1_STR}/push/device-tokens/{token}",
        headers=first_headers,
    )

    device_token_db = db.exec(
        select(DeviceToken).where(DeviceToken.token == token)
    ).first()
    assert device_token_db is None

    # The second user now signs in on the same device and registers.
    r = client.post(
        f"{settings.API_V1_STR}/push/device-tokens",
        headers=second_headers,
        json={"token": token, "platform": "android"},
    )
    assert r.status_code == 200
    second_user_id = client.get(
        f"{settings.API_V1_STR}/users/me", headers=second_headers
    ).json()["id"]
    device_token_db = db.exec(
        select(DeviceToken).where(DeviceToken.token == token)
    ).first()
    assert device_token_db is not None
    assert str(device_token_db.user_id) == second_user_id
