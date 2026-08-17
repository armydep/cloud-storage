from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

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


def test_health_returns_service_metadata(client: TestClient) -> None:
    response = client.get("/api/v1/search/health", headers=auth_headers())

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "index": "files",
        "engine": "elasticsearch",
    }


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
