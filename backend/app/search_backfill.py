import logging

from sqlmodel import Session

from app.core.db import engine
from app.files import repository as files_repository
from app.notifications import repository as notification_repository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def backfill_search_index(*, session: Session, batch_size: int = BATCH_SIZE) -> int:
    """Replay file_created for every existing file through the normal outbox

    path (design doc decision 8) -- search-svc's index is built exclusively
    from events, so making pre-existing files searchable means emitting the
    events they never got, not writing to Elasticsearch directly. Indexing is
    idempotent by file id, so running this twice just re-emits identical
    events; the indexer overwrites the same documents.
    """
    count = 0
    after_id = None
    while True:
        batch = files_repository.list_files_for_search_backfill(
            session=session, batch_size=batch_size, after_id=after_id
        )
        if not batch:
            break
        for file, folder_path in batch:
            notification_repository.enqueue_file_created(
                session=session,
                file_id=file.id,
                owner_id=file.owner_id,
                name=file.name,
                folder_path=folder_path,
                mime_type=file.mime_type,
                category=file.category,
                size_bytes=file.size_bytes,
                created_at=file.created_at,
            )
            after_id = file.id
            count += 1
        session.commit()
    return count


def main() -> None:
    logger.info("Backfilling the search index")
    with Session(engine) as session:
        count = backfill_search_index(session=session)
    logger.info("Enqueued file_created for %s files", count)


if __name__ == "__main__":
    main()
