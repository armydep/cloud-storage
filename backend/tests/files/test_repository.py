import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.files import repository
from app.files.models import Folder
from tests.utils.user import create_random_user


def test_create_root_folder_creates_root(db: Session) -> None:
    user = create_random_user(db)

    folder = repository.create_root_folder(session=db, owner_id=user.id)

    assert folder.path == "root"
    assert folder.name == "root"
    assert folder.owner_id == user.id
    assert folder.parent_id is None


def test_create_root_folder_recovers_from_lost_race(db: Session) -> None:
    """
    Two concurrent first requests can both find no root and both call
    create_root_folder. Reproduce that directly: the second call hits
    uq_folders_owner_path on commit and must return the first call's row
    instead of letting IntegrityError escape.
    """
    user = create_random_user(db)

    first = repository.create_root_folder(session=db, owner_id=user.id)
    second = repository.create_root_folder(session=db, owner_id=user.id)

    assert second.id == first.id


def test_duplicate_owner_path_is_rejected_at_the_database(db: Session) -> None:
    user = create_random_user(db)
    repository.create_root_folder(session=db, owner_id=user.id)

    db.add(Folder(name="root", path="root", owner_id=user.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
