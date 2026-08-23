import uuid

from sqlmodel import Session, select

from app.push import service
from app.push.models import DeviceToken
from tests.utils.user import create_random_user


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
