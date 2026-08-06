from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.files import repository
from app.files.models import FileShare, StoredFile
from tests.utils.user import create_random_user


def _create_file(db: Session) -> StoredFile:
    owner = create_random_user(db)
    folder = repository.create_root_folder(session=db, owner_id=owner.id)
    file = StoredFile(
        owner_id=owner.id,
        folder_id=folder.id,
        name="shared.pdf",
        mime_type="application/pdf",
        category="document",
        blob_hash="a" * 64,
        size_bytes=123,
    )
    db.add(file)
    db.commit()
    db.refresh(file)
    return file


def test_file_share_unique_constraint(db: Session) -> None:
    file = _create_file(db)
    recipient = create_random_user(db)
    repository.create_file_share(
        session=db,
        file_id=file.id,
        recipient_id=recipient.id,
    )

    db.add(FileShare(file_id=file.id, recipient_id=recipient.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_deleting_file_cascades_to_share(db: Session) -> None:
    file = _create_file(db)
    recipient = create_random_user(db)
    share = repository.create_file_share(
        session=db,
        file_id=file.id,
        recipient_id=recipient.id,
    )
    share_id = share.id

    db.delete(file)
    db.commit()

    assert db.get(FileShare, share_id) is None


def test_deleting_recipient_cascades_to_share(db: Session) -> None:
    file = _create_file(db)
    recipient = create_random_user(db)
    share = repository.create_file_share(
        session=db,
        file_id=file.id,
        recipient_id=recipient.id,
    )
    share_id = share.id

    db.delete(recipient)
    db.commit()

    assert db.get(FileShare, share_id) is None


def test_shared_files_are_listed_newest_first(db: Session) -> None:
    older_file = _create_file(db)
    newer_file = _create_file(db)
    recipient = create_random_user(db)
    older_share = repository.create_file_share(
        session=db,
        file_id=older_file.id,
        recipient_id=recipient.id,
    )
    newer_share = repository.create_file_share(
        session=db,
        file_id=newer_file.id,
        recipient_id=recipient.id,
    )
    older_share.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer_share.created_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    db.add(older_share)
    db.add(newer_share)
    db.commit()

    rows = repository.list_files_shared_with_user(
        session=db,
        recipient_id=recipient.id,
    )

    assert [file.id for file, _, _ in rows] == [newer_file.id, older_file.id]
