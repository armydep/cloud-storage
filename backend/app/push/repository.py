import uuid

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import get_datetime_utc
from app.push.models import DeviceToken


def register_device_token(
    *, session: Session, user_id: uuid.UUID, token: str, platform: str
) -> DeviceToken:
    """Register or move a device token to `user_id`.

    `token` is unique globally, not per user (design doc decision 6): the
    same installation registering under a second account must move this row
    rather than create a second one, since that is what makes unregistering
    on logout an enforceable security property rather than best-effort
    hygiene. A fresh insert can still lose a race to a concurrent
    registration of the same token, so that path falls back to the same move
    -- mirroring repository.create_root_folder's recovery from a lost race.
    """
    now = get_datetime_utc()
    existing = session.exec(
        select(DeviceToken).where(DeviceToken.token == token)
    ).first()
    if existing is not None:
        return _move(
            session=session, device_token=existing, user_id=user_id, platform=platform
        )

    device_token = DeviceToken(
        user_id=user_id,
        token=token,
        platform=platform,
        created_at=now,
        last_seen_at=now,
    )
    session.add(device_token)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.exec(
            select(DeviceToken).where(DeviceToken.token == token)
        ).first()
        if existing is None:
            raise
        return _move(
            session=session, device_token=existing, user_id=user_id, platform=platform
        )
    session.refresh(device_token)
    return device_token


def _move(
    *, session: Session, device_token: DeviceToken, user_id: uuid.UUID, platform: str
) -> DeviceToken:
    device_token.user_id = user_id
    device_token.platform = platform
    device_token.last_seen_at = get_datetime_utc()
    session.add(device_token)
    session.commit()
    session.refresh(device_token)
    return device_token


def list_tokens_for_user(*, session: Session, user_id: uuid.UUID) -> list[DeviceToken]:
    """All devices this user has registered.

    One user can hold several (design doc decision 7): the push consumer
    fans out to every row this returns and handles each independently.
    """
    statement = select(DeviceToken).where(DeviceToken.user_id == user_id)
    return list(session.exec(statement).all())


def delete_device_token(*, session: Session, user_id: uuid.UUID, token: str) -> None:
    """Unregister a token, scoped to the caller.

    A no-op if the token is already gone or belongs to a different user --
    idempotent so a retried or duplicated unregister call (e.g. a second
    logout tap) never errors, and so this can never delete another user's
    row.
    """
    statement = select(DeviceToken).where(
        DeviceToken.token == token, DeviceToken.user_id == user_id
    )
    device_token = session.exec(statement).first()
    if device_token is None:
        return
    session.delete(device_token)
    session.commit()
