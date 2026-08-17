import logging
import time
from typing import Any

from elasticsearch import Elasticsearch

from app.broker import SEARCH_QUEUE as QUEUE
from app.broker import EventHandler, RabbitConsumer
from app.config import settings
from app.es_index import ElasticsearchIndex, SearchIndex
from app.events import FILE_CREATED, FILE_DELETED, FOLDER_DELETED

logger = logging.getLogger(__name__)
RECONNECT_INTERVAL_SECONDS = 1.0

_FILE_CREATED_DOCUMENT_FIELDS = (
    "owner_id",
    "name",
    "folder_path",
    "mime_type",
    "category",
    "size_bytes",
    "created_at",
)


def handle_event(
    event_type: str,
    payload: dict[str, Any],
    _message_id: str,
    *,
    index: SearchIndex,
) -> bool:
    if event_type == FILE_CREATED:
        if "file_id" not in payload or not all(
            key in payload for key in _FILE_CREATED_DOCUMENT_FIELDS
        ):
            logger.error("Malformed file_created payload: %s", payload)
            return False
        document = {key: payload[key] for key in _FILE_CREATED_DOCUMENT_FIELDS}
        index.index_document(doc_id=str(payload["file_id"]), document=document)
        return True

    if event_type == FILE_DELETED:
        if "file_id" not in payload:
            logger.error("Malformed file_deleted payload: %s", payload)
            return False
        index.delete_document(doc_id=str(payload["file_id"]))
        return True

    if event_type == FOLDER_DELETED:
        if not {"owner_id", "folder_path"} <= payload.keys():
            logger.error("Malformed folder_deleted payload: %s", payload)
            return False
        index.delete_by_folder_prefix(
            owner_id=str(payload["owner_id"]),
            folder_path=str(payload["folder_path"]),
        )
        return True

    logger.info("Ignoring unsupported search event: %s", event_type)
    return True


def _bind_index(index: SearchIndex) -> EventHandler:
    def handle(event_type: str, payload: dict[str, Any], message_id: str) -> bool:
        return handle_event(event_type, payload, message_id, index=index)

    return handle


def run() -> None:
    logger.info("Search indexer started")
    index = ElasticsearchIndex(Elasticsearch(settings.ELASTICSEARCH_URL))
    index.ensure_index()
    handler = _bind_index(index)

    while True:
        consumer: RabbitConsumer | None = None
        try:
            consumer = RabbitConsumer()
            consumer.consume(handler, queue=QUEUE)
        except Exception:
            logger.exception("Search indexer disconnected; reconnecting")
            time.sleep(RECONNECT_INTERVAL_SECONDS)
        finally:
            if consumer is not None:
                consumer.close()


if __name__ == "__main__":
    run()
