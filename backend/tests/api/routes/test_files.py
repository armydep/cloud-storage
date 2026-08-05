import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.core.storage import ObjectNotFoundError, ObjectStat
from app.files.models import Folder, StoredFile


def test_read_root_creates_user_root(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "root"
    assert content["path"] == "root"
    assert content["parent_id"] is None
    assert content["contents"] == []
    assert "id" in content
    assert "owner_id" in content

    root = db.exec(
        select(Folder).where(Folder.id == content["id"])
    ).first()
    assert root is not None
    assert str(root.owner_id) == content["owner_id"]


def test_read_root_is_idempotent_for_same_user(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    first_response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
    )
    second_response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["id"] == first_response.json()["id"]


def test_read_root_returns_root_contents(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    root_response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
    )
    root = root_response.json()
    child = StoredFile(
        name="report.pdf",
        owner_id=root["owner_id"],
        folder_id=root["id"],
        mime_type="application/pdf",
        category="document",
        blob_hash="abc123",
        size_bytes=12345,
    )
    db.add(child)
    db.commit()
    db.refresh(child)

    response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert len(content["contents"]) == 1
    assert content["contents"][0]["id"] == str(child.id)
    assert content["contents"][0]["name"] == "report.pdf"
    assert content["contents"][0]["type"] == "file"
    assert content["contents"][0]["mime_type"] == "application/pdf"
    assert content["contents"][0]["category"] == "document"
    assert content["contents"][0]["blob_hash"] == "abc123"
    assert content["contents"][0]["size_bytes"] == 12345


def test_read_files_requires_authentication(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/files")

    assert response.status_code == 401


def test_read_root_is_scoped_to_authenticated_user(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    superuser_response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=superuser_token_headers,
    )
    normal_user_response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
    )

    assert superuser_response.status_code == 200
    assert normal_user_response.status_code == 200
    assert superuser_response.json()["id"] != normal_user_response.json()["id"]
    assert (
        superuser_response.json()["owner_id"]
        != normal_user_response.json()["owner_id"]
    )


def test_read_files_by_path(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    root_response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
    )
    root = root_response.json()
    child_folder = Folder(
        name="Documents",
        path="root.documents",
        owner_id=root["owner_id"],
        parent_id=root["id"],
    )
    db.add(child_folder)
    db.commit()
    db.refresh(child_folder)

    response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
        params={"path": "root.documents"},
    )

    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(child_folder.id)
    assert content["name"] == "Documents"
    assert content["path"] == "root.documents"


def test_read_files_by_unknown_path_returns_404(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
        params={"path": "root.missing"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Folder not found"


def _create_unique_folder(
    *,
    client: TestClient,
    headers: dict[str, str],
    db: Session,
    name_prefix: str = "Upload",
) -> Folder:
    root_response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=headers,
    )
    root = root_response.json()
    suffix = uuid.uuid4().hex
    folder = Folder(
        name=f"{name_prefix} {suffix}",
        path=f"root.{name_prefix.lower()}_{suffix}",
        owner_id=root["owner_id"],
        parent_id=root["id"],
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


def test_presign_upload_succeeds_for_owned_folder(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
    )
    calls = []

    def mock_create_presigned_upload_url(*, object_key: str, mime_type: str) -> str:
        calls.append({"object_key": object_key, "mime_type": mime_type})
        return "http://localhost:9000/cloud-file-storage/sha256/upload?sig=1"

    monkeypatch.setattr(
        "app.files.service.storage.create_presigned_upload_url",
        mock_create_presigned_upload_url,
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/presign-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "report.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "a" * 64,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 200
    content = response.json()
    assert content == {
        "upload_url": "http://localhost:9000/cloud-file-storage/sha256/upload?sig=1",
        "method": "PUT",
        "headers": {"Content-Type": "application/pdf"},
        "object_key": f"sha256/{'a' * 64}",
        "expires_in": settings.S3_PRESIGNED_URL_EXPIRES_SECONDS,
    }
    assert calls == [
        {
            "object_key": f"sha256/{'a' * 64}",
            "mime_type": "application/pdf",
        }
    ]


def test_presign_upload_does_not_insert_file(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
    )
    files_before = len(db.exec(select(StoredFile)).all())
    monkeypatch.setattr(
        "app.files.service.storage.create_presigned_upload_url",
        lambda *, object_key, mime_type: "http://localhost:9000/upload",
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/presign-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "report.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "b" * 64,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 200
    files_after = len(db.exec(select(StoredFile)).all())
    assert files_after == files_before


def test_presign_upload_missing_folder_returns_404(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/files/presign-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": f"root.missing_{uuid.uuid4().hex}",
            "name": "report.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "c" * 64,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Folder not found"


def test_presign_upload_invalid_hash_returns_422(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/files/presign-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": "root",
            "name": "report.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "not-a-hash",
            "size_bytes": 123,
        },
    )

    assert response.status_code == 422


def test_presign_upload_requires_authentication(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/files/presign-upload",
        json={
            "folder_path": "root",
            "name": "report.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "d" * 64,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 401


def test_presign_upload_rejects_another_users_folder(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=superuser_token_headers,
        db=db,
        name_prefix="SuperUpload",
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/presign-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "report.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "e" * 64,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Folder not found"


def test_complete_upload_succeeds_for_owned_folder(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="CompleteUpload",
    )
    monkeypatch.setattr(
        "app.files.service.storage.stat_object",
        lambda *, object_key: ObjectStat(
            size_bytes=123,
            content_type="application/pdf",
        ),
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "completed-report.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "f" * 64,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "completed-report.pdf"
    assert content["folder_id"] == str(folder.id)
    assert content["owner_id"] == str(folder.owner_id)
    assert content["mime_type"] == "application/pdf"
    assert content["category"] == "document"
    assert content["blob_hash"] == "f" * 64
    assert content["size_bytes"] == 123

    stored_file = db.exec(
        select(StoredFile).where(StoredFile.id == content["id"])
    ).first()
    assert stored_file is not None


def test_complete_upload_file_appears_in_folder_listing(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="CompleteUploadList",
    )
    monkeypatch.setattr(
        "app.files.service.storage.stat_object",
        lambda *, object_key: ObjectStat(size_bytes=456),
    )

    complete_response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "listed-report.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "1" * 64,
            "size_bytes": 456,
        },
    )
    assert complete_response.status_code == 200

    listing_response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
        params={"path": folder.path},
    )

    assert listing_response.status_code == 200
    contents = listing_response.json()["contents"]
    assert any(item["name"] == "listed-report.pdf" for item in contents)


def test_complete_upload_missing_folder_returns_404(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": f"root.missing_{uuid.uuid4().hex}",
            "name": "report.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "2" * 64,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Folder not found"


def test_complete_upload_missing_object_returns_400(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="CompleteUploadMissingObject",
    )

    def mock_stat_object(*, object_key: str) -> ObjectStat:
        del object_key
        raise ObjectNotFoundError

    monkeypatch.setattr("app.files.service.storage.stat_object", mock_stat_object)

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "missing-object.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "3" * 64,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded object not found"


def test_complete_upload_size_mismatch_returns_400(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="CompleteUploadSizeMismatch",
    )
    monkeypatch.setattr(
        "app.files.service.storage.stat_object",
        lambda *, object_key: ObjectStat(size_bytes=999),
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "size-mismatch.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "4" * 64,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded object size mismatch"


def test_complete_upload_content_type_mismatch_returns_400(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="CompleteUploadContentTypeMismatch",
    )
    monkeypatch.setattr(
        "app.files.service.storage.stat_object",
        lambda *, object_key: ObjectStat(size_bytes=123, content_type="text/plain"),
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "content-type-mismatch.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "5" * 64,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded object content type mismatch"


def test_complete_upload_duplicate_filename_returns_409(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="CompleteUploadDuplicate",
    )
    existing = StoredFile(
        owner_id=folder.owner_id,
        folder_id=folder.id,
        name="duplicate.pdf",
        mime_type="application/pdf",
        category="document",
        blob_hash="6" * 64,
        size_bytes=123,
    )
    db.add(existing)
    db.commit()
    monkeypatch.setattr(
        "app.files.service.storage.stat_object",
        lambda *, object_key: ObjectStat(size_bytes=123),
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "duplicate.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "7" * 64,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "File name already exists"


def test_complete_upload_invalid_payload_returns_422(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": "root",
            "name": "report.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "not-a-hash",
            "size_bytes": 123,
        },
    )

    assert response.status_code == 422


def test_complete_upload_requires_authentication(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        json={
            "folder_path": "root",
            "name": "report.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "8" * 64,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 401


def test_complete_upload_rejects_another_users_folder(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=superuser_token_headers,
        db=db,
        name_prefix="CompleteUploadSuper",
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "report.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": "9" * 64,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Folder not found"
