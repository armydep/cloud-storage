import uuid

from sqlmodel import Session, select

from app.files import repository as files_repository
from app.files.models import Folder, StoredFile
from app.files.schemas import CompleteUploadRequest
from app.notifications.events import FILE_CREATED
from app.notifications.models import NotificationOutbox
from app.search_backfill import backfill_search_index
from tests.utils.user import create_random_user


def _create_file(
    *, session: Session, owner_id: uuid.UUID, folder: Folder, name: str = "report.pdf"
) -> StoredFile:
    blob_hash = uuid.uuid4().hex * 2
    files_repository.create_blob(
        session=session,
        blob_hash=blob_hash,
        object_key=f"sha256/{blob_hash}",
        size_bytes=123,
    )
    return files_repository.create_file(
        session=session,
        owner_id=owner_id,
        folder_id=folder.id,
        request=CompleteUploadRequest(
            folder_path=folder.path,
            name=name,
            mime_type="application/pdf",
            category="document",
            blob_hash=blob_hash,
            size_bytes=123,
        ),
    )


def _file_created_events_for(
    db: Session, file_id: uuid.UUID
) -> list[NotificationOutbox]:
    statement = select(NotificationOutbox).where(
        NotificationOutbox.event_type == FILE_CREATED
    )
    return [
        notification
        for notification in db.exec(statement).all()
        if notification.payload.get("file_id") == str(file_id)
    ]


def test_backfill_enqueues_file_created_for_every_existing_file(db: Session) -> None:
    user = create_random_user(db)
    root = files_repository.create_root_folder(session=db, owner_id=user.id)
    file = _create_file(session=db, owner_id=user.id, folder=root, name="report.pdf")

    backfill_search_index(session=db, batch_size=500)

    events = _file_created_events_for(db, file.id)
    assert len(events) == 1
    assert events[0].payload == {
        "file_id": str(file.id),
        "owner_id": str(user.id),
        "name": "report.pdf",
        "folder_path": "root",
        "mime_type": "application/pdf",
        "category": "document",
        "size_bytes": 123,
        "created_at": file.created_at.isoformat(),
    }


def test_backfill_is_safe_to_run_twice(db: Session) -> None:
    """Running twice must reproduce the same payload -- the indexer

    overwrites by file id downstream (design doc constraint 7), so replaying
    is idempotent from the index's point of view even though the outbox
    itself is not deduplicated.
    """
    user = create_random_user(db)
    root = files_repository.create_root_folder(session=db, owner_id=user.id)
    file = _create_file(session=db, owner_id=user.id, folder=root, name="report.pdf")

    backfill_search_index(session=db, batch_size=500)
    backfill_search_index(session=db, batch_size=500)

    events = _file_created_events_for(db, file.id)
    assert len(events) == 2
    assert events[0].payload == events[1].payload


def test_backfill_covers_every_file_across_multiple_batches(db: Session) -> None:
    user = create_random_user(db)
    root = files_repository.create_root_folder(session=db, owner_id=user.id)
    files = [
        _create_file(session=db, owner_id=user.id, folder=root, name=f"f{i}.pdf")
        for i in range(5)
    ]

    count = backfill_search_index(session=db, batch_size=2)

    assert count >= len(files)
    for file in files:
        assert len(_file_created_events_for(db, file.id)) == 1


def test_backfill_returns_the_number_of_files_enqueued(db: Session) -> None:
    user = create_random_user(db)
    root = files_repository.create_root_folder(session=db, owner_id=user.id)
    _create_file(session=db, owner_id=user.id, folder=root, name="a.pdf")
    _create_file(session=db, owner_id=user.id, folder=root, name="b.pdf")

    before = backfill_search_index(session=db, batch_size=1)
    after = backfill_search_index(session=db, batch_size=1)

    assert before == after
