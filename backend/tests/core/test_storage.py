from typing import Any

import pytest
from botocore.exceptions import ClientError

from app.core import storage
from app.core.config import settings


class MockS3Client:
    def __init__(
        self,
        *,
        presigned_url: str = "http://minio:9000/cloud-file-storage/sha256/abc?sig=1",
        head_response: dict[str, Any] | None = None,
        head_error: ClientError | None = None,
    ) -> None:
        self.presigned_url = presigned_url
        self.head_response = head_response or {
            "ContentLength": 123,
            "ContentType": "text/plain",
        }
        self.head_error = head_error
        self.presigned_calls: list[dict[str, Any]] = []
        self.head_calls: list[dict[str, Any]] = []

    def generate_presigned_url(self, **kwargs: Any) -> str:
        self.presigned_calls.append(kwargs)
        return self.presigned_url

    def head_object(self, **kwargs: Any) -> dict[str, Any]:
        self.head_calls.append(kwargs)
        if self.head_error:
            raise self.head_error
        return self.head_response


def test_get_object_key_is_deterministic() -> None:
    assert storage.get_object_key("abc123") == "sha256/abc123"


def test_create_presigned_upload_url_uses_put_object_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MockS3Client()
    monkeypatch.setattr(storage, "get_s3_client", lambda: client)

    url = storage.create_presigned_upload_url(
        object_key="sha256/abc",
        mime_type="text/plain",
        expires_in=60,
    )

    assert url == "http://localhost:9000/cloud-file-storage/sha256/abc?sig=1"
    assert client.presigned_calls == [
        {
            "ClientMethod": "put_object",
            "Params": {
                "Bucket": settings.S3_BUCKET,
                "Key": "sha256/abc",
                "ContentType": "text/plain",
            },
            "ExpiresIn": 60,
        }
    ]


def test_create_presigned_download_url_uses_get_object_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MockS3Client()
    monkeypatch.setattr(storage, "get_s3_client", lambda: client)

    url = storage.create_presigned_download_url(
        object_key="sha256/abc",
        expires_in=120,
    )

    assert url == "http://localhost:9000/cloud-file-storage/sha256/abc?sig=1"
    assert client.presigned_calls == [
        {
            "ClientMethod": "get_object",
            "Params": {
                "Bucket": settings.S3_BUCKET,
                "Key": "sha256/abc",
            },
            "ExpiresIn": 120,
        }
    ]


def test_create_presigned_url_uses_default_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MockS3Client()
    monkeypatch.setattr(storage, "get_s3_client", lambda: client)

    storage.create_presigned_download_url(object_key="sha256/abc")

    assert client.presigned_calls[0]["ExpiresIn"] == (
        settings.S3_PRESIGNED_URL_EXPIRES_SECONDS
    )


def test_presigned_url_rewrite_keeps_query_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MockS3Client(
        presigned_url="http://minio:9000/cloud-file-storage/sha256/abc?X-Amz-Signature=keep"
    )
    monkeypatch.setattr(storage, "get_s3_client", lambda: client)

    url = storage.create_presigned_download_url(object_key="sha256/abc")

    assert (
        url
        == "http://localhost:9000/cloud-file-storage/sha256/abc?X-Amz-Signature=keep"
    )


def test_stat_object_maps_head_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MockS3Client(
        head_response={
            "ContentLength": 456,
            "ContentType": "application/pdf",
        }
    )
    monkeypatch.setattr(storage, "get_s3_client", lambda: client)

    result = storage.stat_object(object_key="sha256/abc")

    assert result == storage.ObjectStat(size_bytes=456, content_type="application/pdf")
    assert client.head_calls == [
        {
            "Bucket": settings.S3_BUCKET,
            "Key": "sha256/abc",
        }
    ]


def test_stat_object_maps_missing_object(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MockS3Client(
        head_error=ClientError(
            error_response={"Error": {"Code": "404"}},
            operation_name="HeadObject",
        )
    )
    monkeypatch.setattr(storage, "get_s3_client", lambda: client)

    with pytest.raises(storage.ObjectNotFoundError):
        storage.stat_object(object_key="sha256/missing")
