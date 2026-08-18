from typing import Any

import pytest

from app.cursor import InvalidCursorError, encode_cursor
from app.es_index import SearchHit
from app.search_service import execute_search


def _hit(doc_id: str, **overrides: object) -> SearchHit:
    source: dict[str, object] = {
        "owner_id": "owner-1",
        "name": "report.pdf",
        "folder_path": "root.reports",
        "mime_type": "application/pdf",
        "category": "document",
        "size_bytes": 123,
        "created_at": "2026-08-17T00:00:00+00:00",
    }
    source.update(overrides)
    return SearchHit(doc_id=doc_id, source=source, sort=[1.0, 1755388800000, doc_id])


class _FakeSearchIndex:
    def __init__(self, hits: list[SearchHit]) -> None:
        self._hits = hits
        self.calls: list[dict[str, Any]] = []

    def ensure_index(self) -> None:  # pragma: no cover - unused by search_service
        pass

    def index_document(self, *, doc_id: str, document: dict[str, Any]) -> None:
        pass  # pragma: no cover - unused by search_service

    def delete_document(self, *, doc_id: str) -> None:
        pass  # pragma: no cover - unused by search_service

    def delete_by_folder_prefix(self, *, owner_id: str, folder_path: str) -> None:
        pass  # pragma: no cover - unused by search_service

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
        self.calls.append(
            {
                "owner_id": owner_id,
                "folder_path": folder_path,
                "query": query,
                "category": category,
                "limit": limit,
                "search_after": search_after,
            }
        )
        return self._hits[:limit]

    def is_healthy(self) -> bool:  # pragma: no cover - unused by search_service
        return True


def test_execute_search_passes_owner_id_and_limit_plus_one_through() -> None:
    index = _FakeSearchIndex([_hit("a"), _hit("b")])

    execute_search(
        index=index,
        owner_id="owner-1",
        folder_path="root",
        q="report",
        category="document",
        limit=2,
        cursor=None,
    )

    assert index.calls[0] == {
        "owner_id": "owner-1",
        "folder_path": "root",
        "query": "report",
        "category": "document",
        "limit": 3,  # limit + 1, to detect whether a next page exists
        "search_after": None,
    }


def test_execute_search_returns_next_cursor_when_more_results_exist() -> None:
    index = _FakeSearchIndex([_hit("a"), _hit("b"), _hit("c")])

    page = execute_search(
        index=index,
        owner_id="owner-1",
        folder_path="root",
        q=None,
        category=None,
        limit=2,
        cursor=None,
    )

    assert [result.id for result in page.results] == ["a", "b"]
    assert page.next_cursor is not None


def test_execute_search_returns_no_cursor_on_the_last_page() -> None:
    index = _FakeSearchIndex([_hit("a"), _hit("b")])

    page = execute_search(
        index=index,
        owner_id="owner-1",
        folder_path="root",
        q=None,
        category=None,
        limit=2,
        cursor=None,
    )

    assert [result.id for result in page.results] == ["a", "b"]
    assert page.next_cursor is None


def test_execute_search_returns_no_cursor_when_no_results() -> None:
    index = _FakeSearchIndex([])

    page = execute_search(
        index=index,
        owner_id="owner-1",
        folder_path="root",
        q=None,
        category=None,
        limit=2,
        cursor=None,
    )

    assert page.results == []
    assert page.next_cursor is None


def test_execute_search_decodes_cursor_into_search_after() -> None:
    index = _FakeSearchIndex([_hit("a")])
    cursor = encode_cursor([1.0, 1755388800000, "z"])

    execute_search(
        index=index,
        owner_id="owner-1",
        folder_path="root",
        q=None,
        category=None,
        limit=2,
        cursor=cursor,
    )

    assert index.calls[0]["search_after"] == [1.0, 1755388800000, "z"]


def test_execute_search_rejects_an_invalid_cursor_before_querying() -> None:
    index = _FakeSearchIndex([_hit("a")])

    with pytest.raises(InvalidCursorError):
        execute_search(
            index=index,
            owner_id="owner-1",
            folder_path="root",
            q=None,
            category=None,
            limit=2,
            cursor="not-a-valid-cursor!!!",
        )

    assert index.calls == []


def test_execute_search_next_cursor_encodes_the_last_returned_hits_sort() -> None:
    index = _FakeSearchIndex([_hit("a"), _hit("b"), _hit("c")])

    page = execute_search(
        index=index,
        owner_id="owner-1",
        folder_path="root",
        q=None,
        category=None,
        limit=2,
        cursor=None,
    )

    from app.cursor import decode_cursor

    assert page.next_cursor is not None
    assert decode_cursor(page.next_cursor) == _hit("b").sort


def test_execute_search_maps_hit_fields_into_results() -> None:
    index = _FakeSearchIndex(
        [_hit("file-1", name="custom.pdf", folder_path="root.a", mime_type="x/y")]
    )

    page = execute_search(
        index=index,
        owner_id="owner-1",
        folder_path="root",
        q=None,
        category=None,
        limit=1,
        cursor=None,
    )

    result = page.results[0]
    assert result.id == "file-1"
    assert result.name == "custom.pdf"
    assert result.folder_path == "root.a"
    assert result.mime_type == "x/y"
