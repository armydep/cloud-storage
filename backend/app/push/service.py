from sqlmodel import Session

from app.models import User
from app.push import repository
from app.push.schemas import DeviceTokenPublic


def register_device_token(
    *, session: Session, user: User, token: str, platform: str
) -> DeviceTokenPublic:
    device_token = repository.register_device_token(
        session=session, user_id=user.id, token=token, platform=platform
    )
    return DeviceTokenPublic(
        id=device_token.id,
        token=device_token.token,
        platform=device_token.platform,
        created_at=device_token.created_at,
        last_seen_at=device_token.last_seen_at,
    )


def unregister_device_token(*, session: Session, user: User, token: str) -> None:
    repository.delete_device_token(session=session, user_id=user.id, token=token)
