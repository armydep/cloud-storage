from typing import Any

from app.es_index import SearchHit
from app.indexer import handle_event


class _FakeSearchIndex:
    def __init__(self) -> None:
        self.indexed: list[dict[str, Any]] = []
        self.deleted_ids: list[str] = []
        self.deleted_prefixes: list[tuple[str, str]] = []

    def ensure_index(self) -> None:
        pass

    def index_document(self, *, doc_id: str, document: dict[str, Any]) -> None:
        self.indexed.append({"doc_id": doc_id, "document": document})

    def delete_document(self, *, doc_id: str) -> None:
        self.deleted_ids.append(doc_id)

    def delete_by_folder_prefix(self, *, owner_id: str, folder_path: str) -> None:
        self.deleted_prefixes.append((owner_id, folder_path))

    def search(
        self,
        *,
        owner_id: str,
        folder_path: str,
        query: str | None,
        category: str | None,
        limit: int,
        search_after: list[Any] | None,
    ) -> list[SearchHit]:
        raise NotImplementedError("the indexer never queries")  # pragma: no cover

    def is_healthy(self) -> bool:
        raise NotImplementedError("the indexer never checks health")  # pragma: no cover


def test_file_created_indexes_document_by_file_id() -> None:
    index = _FakeSearchIndex()
    payload = {
        "file_id": "file-1",
        "owner_id": "owner-1",
        "name": "report.pdf",
        "folder_path": "root.reports",
        "mime_type": "application/pdf",
        "category": "document",
        "size_bytes": 123,
        "created_at": "2026-08-17T00:00:00+00:00",
    }

    handled = handle_event("file_created", payload, "msg-1", index=index)

    assert handled is True
    assert index.indexed == [
        {
            "doc_id": "file-1",
            "document": {
                "owner_id": "owner-1",
                "name": "report.pdf",
                "folder_path": "root.reports",
                "mime_type": "application/pdf",
                "category": "document",
                "size_bytes": 123,
                "created_at": "2026-08-17T00:00:00+00:00",
            },
        }
    ]


def test_file_created_redelivery_overwrites_the_same_document() -> None:
    index = _FakeSearchIndex()
    payload = {
        "file_id": "file-1",
        "owner_id": "owner-1",
        "name": "report.pdf",
        "folder_path": "root.reports",
        "mime_type": "application/pdf",
        "category": "document",
        "size_bytes": 123,
        "created_at": "2026-08-17T00:00:00+00:00",
    }

    handle_event("file_created", payload, "msg-1", index=index)
    handle_event("file_created", payload, "msg-1-retry", index=index)

    assert [item["doc_id"] for item in index.indexed] == ["file-1", "file-1"]


def test_file_created_missing_required_field_is_not_handled() -> None:
    index = _FakeSearchIndex()
    payload = {"file_id": "file-1", "owner_id": "owner-1"}

    handled = handle_event("file_created", payload, "msg-1", index=index)

    assert handled is False
    assert index.indexed == []


def test_file_deleted_deletes_document_by_file_id() -> None:
    index = _FakeSearchIndex()

    handled = handle_event(
        "file_deleted",
        {"file_id": "file-1", "owner_id": "owner-1"},
        "msg-1",
        index=index,
    )

    assert handled is True
    assert index.deleted_ids == ["file-1"]


def test_file_deleted_missing_file_id_is_not_handled() -> None:
    index = _FakeSearchIndex()

    handled = handle_event(
        "file_deleted", {"owner_id": "owner-1"}, "msg-1", index=index
    )

    assert handled is False
    assert index.deleted_ids == []


def test_folder_deleted_deletes_by_owner_and_path_prefix() -> None:
    index = _FakeSearchIndex()

    handled = handle_event(
        "folder_deleted",
        {"owner_id": "owner-1", "folder_path": "root.reports"},
        "msg-1",
        index=index,
    )

    assert handled is True
    assert index.deleted_prefixes == [("owner-1", "root.reports")]


def test_folder_deleted_missing_fields_is_not_handled() -> None:
    index = _FakeSearchIndex()

    handled = handle_event(
        "folder_deleted", {"owner_id": "owner-1"}, "msg-1", index=index
    )

    assert handled is False
    assert index.deleted_prefixes == []


def test_unsupported_event_is_ignored_and_acked() -> None:
    index = _FakeSearchIndex()

    handled = handle_event("file_shared", {}, "msg-1", index=index)

    assert handled is True
    assert index.indexed == []
    assert index.deleted_ids == []
    assert index.deleted_prefixes == []
