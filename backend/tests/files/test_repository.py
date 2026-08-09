import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.files import repository
from app.files.models import FileBlob, Folder
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


def test_create_blob_persists_blob_metadata(db: Session) -> None:
    blob_hash = uuid.uuid4().hex * 2

    blob = repository.create_blob(
        session=db,
        blob_hash=blob_hash,
        object_key=f"sha256/{blob_hash}",
        size_bytes=123,
    )
    db.commit()

    stored_blob = db.get(FileBlob, blob_hash)
    assert stored_blob is not None
    assert stored_blob.blob_hash == blob.blob_hash
    assert stored_blob.object_key == f"sha256/{blob_hash}"
    assert stored_blob.size_bytes == 123
    assert stored_blob.ref_count == 0


def test_blob_ref_count_can_be_incremented(db: Session) -> None:
    blob_hash = uuid.uuid4().hex * 2
    blob = repository.create_blob(
        session=db,
        blob_hash=blob_hash,
        object_key=f"sha256/{blob_hash}",
        size_bytes=123,
        ref_count=1,
    )

    repository.increment_blob_ref_count(blob=blob)
    db.commit()

    db.expire_all()
    stored_blob = db.get(FileBlob, blob_hash)
    assert stored_blob is not None
    assert stored_blob.ref_count == 2


def test_duplicate_blob_hash_is_rejected_at_the_database(db: Session) -> None:
    blob_hash = uuid.uuid4().hex * 2
    repository.create_blob(
        session=db,
        blob_hash=blob_hash,
        object_key=f"sha256/{blob_hash}",
        size_bytes=123,
    )
    db.commit()

    with pytest.raises(repository.DuplicateFileBlobRepositoryError):
        repository.create_blob(
            session=db,
            blob_hash=blob_hash,
            object_key=f"sha256/{blob_hash}-duplicate",
            size_bytes=123,
        )
