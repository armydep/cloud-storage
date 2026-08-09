import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.files import repository
from app.files.models import FileBlob, Folder, StoredFile
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


def test_delete_blob_marks_blob_for_deletion(db: Session) -> None:
    blob_hash = uuid.uuid4().hex * 2
    blob = repository.create_blob(
        session=db,
        blob_hash=blob_hash,
        object_key=f"sha256/{blob_hash}",
        size_bytes=123,
    )

    repository.delete_blob(session=db, blob=blob)
    db.commit()

    assert db.get(FileBlob, blob_hash) is None


def test_delete_file_marks_file_for_deletion(db: Session) -> None:
    user = create_random_user(db)
    folder = repository.create_root_folder(session=db, owner_id=user.id)
    blob_hash = uuid.uuid4().hex * 2
    repository.create_blob(
        session=db,
        blob_hash=blob_hash,
        object_key=f"sha256/{blob_hash}",
        size_bytes=123,
        ref_count=1,
    )
    file = StoredFile(
        owner_id=user.id,
        folder_id=folder.id,
        name=f"{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        category="document",
        blob_hash=blob_hash,
        size_bytes=123,
    )
    db.add(file)
    db.commit()
    db.refresh(file)

    repository.delete_file(session=db, file=file)
    db.commit()

    assert db.get(StoredFile, file.id) is None


def test_list_folder_subtree_returns_target_and_descendants_deepest_first(
    db: Session,
) -> None:
    user = create_random_user(db)
    root = repository.create_root_folder(session=db, owner_id=user.id)
    parent = repository.create_folder(
        session=db,
        owner_id=user.id,
        parent_id=root.id,
        name=f"Parent {uuid.uuid4().hex}",
        path=f"root.parent_{uuid.uuid4().hex}",
    )
    child = repository.create_folder(
        session=db,
        owner_id=user.id,
        parent_id=parent.id,
        name=f"Child {uuid.uuid4().hex}",
        path=f"{parent.path}.child_{uuid.uuid4().hex}",
    )
    sibling = repository.create_folder(
        session=db,
        owner_id=user.id,
        parent_id=root.id,
        name=f"Sibling {uuid.uuid4().hex}",
        path=f"root.sibling_{uuid.uuid4().hex}",
    )

    subtree = repository.list_folder_subtree(
        session=db,
        owner_id=user.id,
        path=parent.path,
    )

    assert [folder.id for folder in subtree] == [child.id, parent.id]
    assert sibling.id not in {folder.id for folder in subtree}


def test_list_files_in_folders_returns_only_owned_files_in_requested_folders(
    db: Session,
) -> None:
    user = create_random_user(db)
    other_user = create_random_user(db)
    root = repository.create_root_folder(session=db, owner_id=user.id)
    other_root = repository.create_root_folder(session=db, owner_id=other_user.id)
    target_folder = repository.create_folder(
        session=db,
        owner_id=user.id,
        parent_id=root.id,
        name=f"Target {uuid.uuid4().hex}",
        path=f"root.target_{uuid.uuid4().hex}",
    )
    other_folder = repository.create_folder(
        session=db,
        owner_id=other_user.id,
        parent_id=other_root.id,
        name=f"Other {uuid.uuid4().hex}",
        path=f"root.other_{uuid.uuid4().hex}",
    )
    blob_hash = uuid.uuid4().hex * 2
    repository.create_blob(
        session=db,
        blob_hash=blob_hash,
        object_key=f"sha256/{blob_hash}",
        size_bytes=123,
        ref_count=2,
    )
    target_file = StoredFile(
        owner_id=user.id,
        folder_id=target_folder.id,
        name=f"target-{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        category="document",
        blob_hash=blob_hash,
        size_bytes=123,
    )
    other_file = StoredFile(
        owner_id=other_user.id,
        folder_id=other_folder.id,
        name=f"other-{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        category="document",
        blob_hash=blob_hash,
        size_bytes=123,
    )
    db.add(target_file)
    db.add(other_file)
    db.commit()
    db.refresh(target_file)
    db.refresh(other_file)

    files = repository.list_files_in_folders(
        session=db,
        owner_id=user.id,
        folder_ids=[target_folder.id, other_folder.id],
    )

    assert [file.id for file in files] == [target_file.id]
