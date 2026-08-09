from typing import Any

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from prometheus_client import generate_latest
from sqlalchemy import text
from sqlmodel import Session

from app.core import storage
from app.core.config import settings
from tests.utils.item import create_random_item


class MetricsMockS3Client:
    def __init__(self, *, head_error: ClientError | None = None) -> None:
        self.head_error = head_error

    def generate_presigned_url(self, **_kwargs: Any) -> str:
        return "http://minio:9000/cloud-file-storage/sha256/abc?sig=1"

    def head_object(self, **_kwargs: Any) -> dict[str, Any]:
        if self.head_error:
            raise self.head_error
        return {"ContentLength": 123, "ContentType": "text/plain"}


def test_metrics_endpoint_requires_bearer_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "METRICS_BEARER_TOKEN", "test-token")

    missing_response = client.get("/metrics")
    wrong_response = client.get(
        "/metrics",
        headers={"Authorization": "Bearer wrong-token"},
    )
    valid_response = client.get(
        "/metrics",
        headers={"Authorization": "Bearer test-token"},
    )

    assert missing_response.status_code == 401
    assert missing_response.headers["www-authenticate"] == "Bearer"
    assert wrong_response.status_code == 403
    assert valid_response.status_code == 200
    assert valid_response.headers["content-type"].startswith("text/plain")
    assert "http_requests_total" in valid_response.text


def test_metrics_endpoint_is_disabled_without_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "METRICS_BEARER_TOKEN", None)

    response = client.get("/metrics")

    assert response.status_code == 404


def test_request_metrics_use_route_template_labels(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "METRICS_BEARER_TOKEN", "test-token")

    health_response = client.get(f"{settings.API_V1_STR}/utils/health-check/")
    metrics_response = client.get(
        "/metrics",
        headers={"Authorization": "Bearer test-token"},
    )

    assert health_response.status_code == 200
    assert metrics_response.status_code == 200
    assert (
        'http_requests_total{endpoint="/api/v1/utils/health-check/",'
        'method="GET",status_code="200"}'
    ) in metrics_response.text


def test_request_metrics_use_parameterized_route_template_labels(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "METRICS_BEARER_TOKEN", "test-token")
    item = create_random_item(db)

    item_response = client.get(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=superuser_token_headers,
    )
    metrics_response = client.get(
        "/metrics",
        headers={"Authorization": "Bearer test-token"},
    )

    assert item_response.status_code == 200
    assert metrics_response.status_code == 200
    assert (
        'http_requests_total{endpoint="/api/v1/items/{id}",'
        'method="GET",status_code="200"}'
    ) in metrics_response.text
    assert str(item.id) not in metrics_response.text


def test_storage_operation_metrics_record_success_and_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    successful_client = MetricsMockS3Client()
    monkeypatch.setattr(storage, "get_s3_client", lambda: successful_client)

    storage.create_presigned_download_url(
        object_key="sha256/abc",
        filename="report.pdf",
    )

    missing_client = MetricsMockS3Client(
        head_error=ClientError(
            error_response={"Error": {"Code": "404"}},
            operation_name="HeadObject",
        )
    )
    monkeypatch.setattr(storage, "get_s3_client", lambda: missing_client)

    with pytest.raises(storage.ObjectNotFoundError):
        storage.stat_object(object_key="sha256/missing")

    metrics = generate_latest().decode()

    assert (
        'object_storage_operations_total{operation="create_presigned_download_url",'
        'result="success"}'
    ) in metrics
    assert (
        'object_storage_operations_total{operation="stat_object",result="error"}'
        in (metrics)
    )


def test_database_pool_metrics_are_exposed(db: Session) -> None:
    db.exec(text("SELECT 1"))

    metrics = generate_latest().decode()

    assert "db_pool_checked_out_connections" in metrics
    assert "db_pool_checked_in_connections" in metrics
    assert "db_pool_size_connections" in metrics
    assert "db_pool_overflow_connections" in metrics
    assert "db_pool_checkout_wait_seconds" in metrics
