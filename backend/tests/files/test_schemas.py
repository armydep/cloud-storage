import pytest
from pydantic import ValidationError

from app.files.schemas import (
    CompleteUploadRequest,
    FileCategory,
    FolderCreate,
    PresignDownloadResponse,
    PresignUploadRequest,
    PresignUploadResponse,
)

VALID_HASH = "a" * 64


def test_folder_create_trims_name() -> None:
    request = FolderCreate(parent_path="root.documents", name="  Project Files  ")

    assert request.name == "Project Files"


@pytest.mark.parametrize("name", ["", "   ", "reports/2026"])
def test_folder_create_rejects_invalid_name(name: str) -> None:
    with pytest.raises(ValidationError):
        FolderCreate(parent_path="root", name=name)


def valid_payload() -> dict[str, object]:
    return {
        "folder_path": "root.documents.phase_2",
        "name": "report.pdf",
        "mime_type": "application/pdf",
        "category": "document",
        "blob_hash": VALID_HASH,
        "size_bytes": 123,
    }


def test_presign_upload_request_accepts_valid_payload() -> None:
    request = PresignUploadRequest.model_validate(valid_payload())

    assert request.folder_path == "root.documents.phase_2"
    assert request.name == "report.pdf"
    assert request.mime_type == "application/pdf"
    assert request.category == FileCategory.document
    assert request.blob_hash == VALID_HASH
    assert request.size_bytes == 123


def test_complete_upload_request_accepts_valid_payload() -> None:
    request = CompleteUploadRequest.model_validate(valid_payload())

    assert request.folder_path == "root.documents.phase_2"
    assert request.blob_hash == VALID_HASH


def test_blob_hash_is_normalized_to_lowercase() -> None:
    payload = valid_payload()
    payload["blob_hash"] = "A" * 64

    request = PresignUploadRequest.model_validate(payload)

    assert request.blob_hash == "a" * 64


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("blob_hash", "a" * 63),
        ("blob_hash", "g" * 64),
        ("size_bytes", 0),
        ("folder_path", ""),
        ("folder_path", "root..documents"),
        ("folder_path", "root.documents-with-dash"),
        ("folder_path", "1root.documents"),
        ("name", "folder/report.pdf"),
        ("category", "binary"),
    ],
)
def test_upload_request_rejects_invalid_values(field: str, value: object) -> None:
    payload = valid_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        PresignUploadRequest.model_validate(payload)


def test_complete_upload_request_rejects_invalid_values() -> None:
    payload = valid_payload()
    payload["name"] = "nested/report.pdf"

    with pytest.raises(ValidationError):
        CompleteUploadRequest.model_validate(payload)


def test_presign_upload_response_defaults_method_to_put() -> None:
    response = PresignUploadResponse(
        upload_url="http://localhost:9000/bucket/key",
        headers={"Content-Type": "application/pdf"},
        object_key="sha256/abc",
        expires_in=900,
    )

    assert response.method == "PUT"


def test_presign_download_response_defaults_method_to_get() -> None:
    response = PresignDownloadResponse(
        download_url="http://localhost:9000/bucket/key",
        expires_in=900,
    )

    assert response.method == "GET"
