import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app import crud
from app.models import Folder
from tests.utils.user import create_random_user


def test_get_or_create_root_folder_creates_root(db: Session) -> None:
    user = create_random_user(db)

    folder = crud.get_or_create_root_folder(session=db, owner_id=user.id)

    assert folder.path == "root"
    assert folder.name == "root"
    assert folder.owner_id == user.id
    assert folder.parent_id is None


def test_get_or_create_root_folder_is_idempotent(db: Session) -> None:
    user = create_random_user(db)

    first = crud.get_or_create_root_folder(session=db, owner_id=user.id)
    second = crud.get_or_create_root_folder(session=db, owner_id=user.id)

    assert first.id == second.id


def test_duplicate_owner_path_is_rejected(db: Session) -> None:
    user = create_random_user(db)
    crud.get_or_create_root_folder(session=db, owner_id=user.id)

    db.add(Folder(name="root", path="root", owner_id=user.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_get_or_create_root_folder_recovers_from_lost_race(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A concurrent request can insert the root between our lookup and our insert.
    Simulate that by making the lookup miss a root that already exists, so the
    insert hits uq_folders_owner_path and the helper must return the existing
    row instead of raising.
    """
    user = create_random_user(db)
    existing = crud.get_or_create_root_folder(session=db, owner_id=user.id)

    monkeypatch.setattr(crud, "get_folder_by_path", lambda **kwargs: None)
    folder = crud.get_or_create_root_folder(session=db, owner_id=user.id)

    assert folder.id == existing.id
