import uuid

import pytest
from sqlmodel import Session, select

from app.push import repository
from app.push.models import DeviceToken
from tests.utils.user import create_random_user


def test_register_device_token_creates_a_row(db: Session) -> None:
    user = create_random_user(db)
    token = uuid.uuid4().hex

    device_token = repository.register_device_token(
        session=db, user_id=user.id, token=token, platform="android"
    )

    assert device_token.user_id == user.id
    assert device_token.token == token
    assert device_token.platform == "android"
    assert device_token.created_at == device_token.last_seen_at


def test_register_device_token_is_idempotent_for_the_same_user(db: Session) -> None:
    user = create_random_user(db)
    token = uuid.uuid4().hex

    first = repository.register_device_token(
        session=db, user_id=user.id, token=token, platform="android"
    )
    second = repository.register_device_token(
        session=db, user_id=user.id, token=token, platform="android"
    )

    assert first.id == second.id
    rows = db.exec(select(DeviceToken).where(DeviceToken.token == token)).all()
    assert len(rows) == 1


def test_register_device_token_recovers_from_lost_insert_race(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh insert can lose a race to a concurrent registration of the

    same token: another transaction commits a row between this function's
    own upfront existence check and its insert. Reproduced deterministically
    by making that upfront check miss a row that genuinely already exists,
    forcing the insert to hit the unique constraint for real and exercising
    the IntegrityError recovery path -- mirrors
    repository.create_root_folder's own lost-race recovery.
    """
    user = create_random_user(db)
    other_user = create_random_user(db)
    token = uuid.uuid4().hex
    repository.register_device_token(
        session=db, user_id=other_user.id, token=token, platform="android"
    )

    real_exec = db.exec
    calls = {"n": 0}

    class _EmptyResult:
        def first(self) -> None:
            return None

    def exec_missing_first_lookup(statement, *args, **kwargs):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:
            return _EmptyResult()
        return real_exec(statement, *args, **kwargs)

    monkeypatch.setattr(db, "exec", exec_missing_first_lookup)

    moved = repository.register_device_token(
        session=db, user_id=user.id, token=token, platform="android"
    )

    assert moved.user_id == user.id
    monkeypatch.undo()
    rows = db.exec(select(DeviceToken).where(DeviceToken.token == token)).all()
    assert len(rows) == 1


def test_register_device_token_moves_between_users_without_duplicating(
    db: Session,
) -> None:
    """The security-critical property (design doc decision 6): the same

    installation registering under a second account must move the row, not
    create a second one -- this is what makes unregister-on-logout an
    enforceable guarantee rather than best-effort.
    """
    first_user = create_random_user(db)
    second_user = create_random_user(db)
    token = uuid.uuid4().hex

    repository.register_device_token(
        session=db, user_id=first_user.id, token=token, platform="android"
    )
    moved = repository.register_device_token(
        session=db, user_id=second_user.id, token=token, platform="android"
    )

    rows = db.exec(select(DeviceToken).where(DeviceToken.token == token)).all()
    assert len(rows) == 1
    assert moved.user_id == second_user.id


def test_register_device_token_updates_last_seen_at(db: Session) -> None:
    user = create_random_user(db)
    token = uuid.uuid4().hex

    first = repository.register_device_token(
        session=db, user_id=user.id, token=token, platform="android"
    )
    second = repository.register_device_token(
        session=db, user_id=user.id, token=token, platform="android"
    )

    assert second.last_seen_at >= first.last_seen_at


def test_one_user_can_hold_several_device_tokens(db: Session) -> None:
    user = create_random_user(db)

    repository.register_device_token(
        session=db, user_id=user.id, token=uuid.uuid4().hex, platform="android"
    )
    repository.register_device_token(
        session=db, user_id=user.id, token=uuid.uuid4().hex, platform="android"
    )

    rows = db.exec(select(DeviceToken).where(DeviceToken.user_id == user.id)).all()
    assert len(rows) == 2


def test_delete_device_token_removes_the_row(db: Session) -> None:
    user = create_random_user(db)
    token = uuid.uuid4().hex
    repository.register_device_token(
        session=db, user_id=user.id, token=token, platform="android"
    )

    repository.delete_device_token(session=db, user_id=user.id, token=token)

    assert (
        db.exec(select(DeviceToken).where(DeviceToken.token == token)).first() is None
    )


def test_delete_device_token_is_a_noop_when_missing(db: Session) -> None:
    user = create_random_user(db)

    repository.delete_device_token(
        session=db, user_id=user.id, token="never-registered"
    )


def test_delete_device_token_does_not_remove_another_users_token(db: Session) -> None:
    """Unregister must be scoped to the caller -- otherwise any signed-in

    user could delete another user's device registration by guessing or
    replaying a token value.
    """
    owner = create_random_user(db)
    other_user = create_random_user(db)
    token = uuid.uuid4().hex
    repository.register_device_token(
        session=db, user_id=owner.id, token=token, platform="android"
    )

    repository.delete_device_token(session=db, user_id=other_user.id, token=token)

    device_token_db = db.exec(
        select(DeviceToken).where(DeviceToken.token == token)
    ).first()
    assert device_token_db is not None
    assert device_token_db.user_id == owner.id


def test_deleting_a_user_cascades_to_their_device_tokens(db: Session) -> None:
    user = create_random_user(db)
    token = uuid.uuid4().hex
    repository.register_device_token(
        session=db, user_id=user.id, token=token, platform="android"
    )

    db.delete(user)
    db.commit()

    assert (
        db.exec(select(DeviceToken).where(DeviceToken.token == token)).first() is None
    )
