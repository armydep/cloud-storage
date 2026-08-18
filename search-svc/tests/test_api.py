import uuid
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from app.cursor import decode_cursor
from app.es_index import SearchHit, SearchIndexUnavailableError
from app.main import app, get_search_index
from app.security import ALGORITHM

TEST_SECRET_KEY = "search-service-test-secret-at-least-32-bytes"


def auth_headers(
    *, secret_key: str = TEST_SECRET_KEY, subject: str = "user-id"
) -> dict[str, str]:
    token = jwt.encode(
        {
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "sub": subject,
        },
        secret_key,
        algorithm=ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def _hit(doc_id: str, **overrides: object) -> SearchHit:
    source: dict[str, object] = {
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
    """A protocol-conformant double. test_api.py never touches a real

    Elasticsearch -- that behavior is covered by tests/test_es_index.py's
    testcontainer suite and tests/test_query.py's pure query-builder tests.
    This fixture only proves the HTTP layer wires the token subject, cursor,
    and error mapping correctly.
    """

    def __init__(self) -> None:
        self.hits: list[SearchHit] = []
        self.healthy = True
        self.raise_unavailable = False
        self.search_calls: list[dict[str, Any]] = []

    def ensure_index(self) -> None:  # pragma: no cover - unused by main.py
        pass

    def index_document(self, *, doc_id: str, document: dict[str, Any]) -> None:
        pass  # pragma: no cover - unused by main.py

    def delete_document(self, *, doc_id: str) -> None:
        pass  # pragma: no cover - unused by main.py

    def delete_by_folder_prefix(self, *, owner_id: str, folder_path: str) -> None:
        pass  # pragma: no cover - unused by main.py

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
        if self.raise_unavailable:
            raise SearchIndexUnavailableError("unreachable")
        self.search_calls.append(
            {
                "owner_id": owner_id,
                "folder_path": folder_path,
                "query": query,
                "category": category,
                "limit": limit,
                "search_after": search_after,
            }
        )
        return self.hits[:limit]

    def is_healthy(self) -> bool:
        return self.healthy


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def fake_index() -> Generator[_FakeSearchIndex, None, None]:
    fake = _FakeSearchIndex()
    app.dependency_overrides[get_search_index] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_search_index, None)


def test_search_returns_empty_results(client: TestClient) -> None:
    response = client.get(
        "/api/v1/search/files",
        params={"folder_path": "root.reports_2026", "limit": 100},
        headers=auth_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {"results": [], "next_cursor": None}


def test_search_requires_folder_path(client: TestClient) -> None:
    response = client.get("/api/v1/search/files", headers=auth_headers())

    assert response.status_code == 422


@pytest.mark.parametrize(
    "folder_path",
    ["", "1root", "root..reports", "root/reports", "root.reports-2026"],
)
def test_search_rejects_malformed_ltree_paths(
    client: TestClient, folder_path: str
) -> None:
    response = client.get(
        "/api/v1/search/files",
        params={"folder_path": folder_path},
        headers=auth_headers(),
    )

    assert response.status_code == 422


def test_search_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/api/v1/search/files", params={"folder_path": "root"})

    assert response.status_code == 401


def test_search_rejects_token_signed_with_wrong_key(client: TestClient) -> None:
    response = client.get(
        "/api/v1/search/files",
        params={"folder_path": "root"},
        headers=auth_headers(secret_key="wrong-search-secret-at-least-32-bytes"),
    )

    assert response.status_code == 403


def test_search_rejects_token_without_subject(client: TestClient) -> None:
    token = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        TEST_SECRET_KEY,
        algorithm=ALGORITHM,
    )

    response = client.get(
        "/api/v1/search/files",
        params={"folder_path": "root"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_search_uses_the_authenticated_subject_as_owner_id(
    client: TestClient, fake_index: _FakeSearchIndex
) -> None:
    response = client.get(
        "/api/v1/search/files",
        params={"folder_path": "root.reports"},
        headers=auth_headers(subject="user-alpha"),
    )

    assert response.status_code == 200
    assert fake_index.search_calls[-1]["owner_id"] == "user-alpha"


def test_search_scopes_each_request_to_its_own_authenticated_subject(
    client: TestClient, fake_index: _FakeSearchIndex
) -> None:
    """Two different users, same endpoint, same process. Nothing about how

    owner_id reaches the query depends on request order or shared state.
    """
    client.get(
        "/api/v1/search/files",
        params={"folder_path": "root"},
        headers=auth_headers(subject="user-a"),
    )
    client.get(
        "/api/v1/search/files",
        params={"folder_path": "root"},
        headers=auth_headers(subject="user-b"),
    )

    assert [call["owner_id"] for call in fake_index.search_calls] == [
        "user-a",
        "user-b",
    ]


def test_search_passes_q_category_and_folder_path_through(
    client: TestClient, fake_index: _FakeSearchIndex
) -> None:
    response = client.get(
        "/api/v1/search/files",
        params={
            "folder_path": "root.docs",
            "q": "report",
            "category": "document",
            "limit": 25,
        },
        headers=auth_headers(),
    )

    assert response.status_code == 200
    call = fake_index.search_calls[-1]
    assert call["folder_path"] == "root.docs"
    assert call["query"] == "report"
    assert call["category"] == "document"
    assert call["limit"] == 26  # limit + 1, see app/search_service.py


def test_search_returns_mapped_result_fields(
    client: TestClient, fake_index: _FakeSearchIndex
) -> None:
    file_id = str(uuid.uuid4())
    fake_index.hits = [
        _hit(
            file_id,
            name="report.pdf",
            folder_path="root.reports",
            mime_type="application/pdf",
            category="document",
            size_bytes=456,
            created_at="2026-08-17T12:00:00+00:00",
        )
    ]

    response = client.get(
        "/api/v1/search/files",
        params={"folder_path": "root.reports"},
        headers=auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["results"] == [
        {
            "id": file_id,
            "name": "report.pdf",
            "folder_path": "root.reports",
            "mime_type": "application/pdf",
            "category": "document",
            "size_bytes": 456,
            "created_at": "2026-08-17T12:00:00Z",
        }
    ]
    assert body["next_cursor"] is None


def test_search_next_cursor_round_trips_into_search_after(
    client: TestClient, fake_index: _FakeSearchIndex
) -> None:
    fake_index.hits = [_hit(str(uuid.uuid4())) for _ in range(3)]

    first = client.get(
        "/api/v1/search/files",
        params={"folder_path": "root.reports", "limit": 2},
        headers=auth_headers(),
    )
    assert first.status_code == 200
    cursor = first.json()["next_cursor"]
    assert cursor is not None

    second = client.get(
        "/api/v1/search/files",
        params={"folder_path": "root.reports", "limit": 2, "cursor": cursor},
        headers=auth_headers(),
    )

    assert second.status_code == 200
    assert fake_index.search_calls[-1]["search_after"] == decode_cursor(cursor)


def test_search_rejects_an_invalid_cursor(
    client: TestClient, fake_index: _FakeSearchIndex
) -> None:
    response = client.get(
        "/api/v1/search/files",
        params={"folder_path": "root.reports", "cursor": "not-a-valid-cursor!!!"},
        headers=auth_headers(),
    )

    assert response.status_code == 422
    assert fake_index.search_calls == []


def test_search_returns_503_when_elasticsearch_is_unreachable(
    client: TestClient, fake_index: _FakeSearchIndex
) -> None:
    fake_index.raise_unavailable = True

    response = client.get(
        "/api/v1/search/files",
        params={"folder_path": "root.reports"},
        headers=auth_headers(),
    )

    assert response.status_code == 503


def test_health_returns_service_metadata_when_index_is_healthy(
    client: TestClient, fake_index: _FakeSearchIndex
) -> None:
    fake_index.healthy = True

    response = client.get("/api/v1/search/health", headers=auth_headers())

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "index": "files",
        "engine": "elasticsearch",
    }


def test_health_returns_503_when_index_is_unhealthy(
    client: TestClient, fake_index: _FakeSearchIndex
) -> None:
    fake_index.healthy = False

    response = client.get("/api/v1/search/health", headers=auth_headers())

    assert response.status_code == 503


def test_health_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/api/v1/search/health")

    assert response.status_code == 401


def _parameters_by_name(openapi: dict[str, Any]) -> dict[str, dict[str, Any]]:
    parameters = openapi["paths"]["/api/v1/search/files"]["get"]["parameters"]
    return {parameter["name"]: parameter for parameter in parameters}


def test_query_constraints_are_in_openapi(client: TestClient) -> None:
    response = client.get("/api/v1/search/openapi.json")
    parameters = _parameters_by_name(response.json())

    assert parameters["folder_path"]["required"] is True
    assert parameters["folder_path"]["schema"]["minLength"] == 1
    assert parameters["folder_path"]["schema"]["maxLength"] == 1024
    assert parameters["folder_path"]["schema"]["pattern"]
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 100
