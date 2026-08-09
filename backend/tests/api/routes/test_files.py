import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.core.db import engine
from app.core.storage import ObjectNotFoundError, ObjectStat
from app.files.models import (
    FileBlob,
    FileBlobClaim,
    FileShare,
    Folder,
    PendingUpload,
    StoredFile,
)
from app.files.service import BlobIntegrityError
from app.models import UserCreate
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import random_email


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

    root = db.exec(select(Folder).where(Folder.id == content["id"])).first()
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


def test_create_folder_in_root(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    suffix = uuid.uuid4().hex
    name = f"Project Files {suffix}"
    response = client.post(
        f"{settings.API_V1_STR}/files/folders",
        headers=normal_user_token_headers,
        json={"parent_path": "root", "name": name},
    )

    assert response.status_code == 201
    folder = response.json()
    assert folder["name"] == name
    assert folder["path"] == f"root.project_files_{suffix}"
    assert folder["parent_id"] is not None

    contents_response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
    )
    assert contents_response.status_code == 200
    created_entry = next(
        entry
        for entry in contents_response.json()["contents"]
        if entry["id"] == folder["id"]
    )
    assert created_entry["name"] == name
    assert created_entry["type"] == "folder"
    assert created_entry["path"] == f"root.project_files_{suffix}"


def test_create_nested_folder(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    suffix = uuid.uuid4().hex
    parent_name = f"Projects {suffix}"
    parent_response = client.post(
        f"{settings.API_V1_STR}/files/folders",
        headers=normal_user_token_headers,
        json={"parent_path": "root", "name": parent_name},
    )
    assert parent_response.status_code == 201

    response = client.post(
        f"{settings.API_V1_STR}/files/folders",
        headers=normal_user_token_headers,
        json={
            "parent_path": f"root.projects_{suffix}",
            "name": "2026 Plans",
        },
    )

    assert response.status_code == 201
    assert response.json()["path"] == f"root.projects_{suffix}._2026_plans"
    assert response.json()["parent_id"] == parent_response.json()["id"]


def test_create_duplicate_folder_returns_409(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    suffix = uuid.uuid4().hex
    url = f"{settings.API_V1_STR}/files/folders"
    first_response = client.post(
        url,
        headers=normal_user_token_headers,
        json={"parent_path": "root", "name": f"Project Files {suffix}"},
    )
    second_response = client.post(
        url,
        headers=normal_user_token_headers,
        json={"parent_path": "root", "name": f"Project-Files-{suffix}"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Folder name already exists"


def test_create_folder_in_missing_parent_returns_404(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/files/folders",
        headers=normal_user_token_headers,
        json={"parent_path": "root.missing", "name": "Reports"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Parent folder not found"


def test_create_folder_rejects_another_users_parent(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    suffix = uuid.uuid4().hex
    parent_response = client.post(
        f"{settings.API_V1_STR}/files/folders",
        headers=superuser_token_headers,
        json={"parent_path": "root", "name": f"Private {suffix}"},
    )
    assert parent_response.status_code == 201

    response = client.post(
        f"{settings.API_V1_STR}/files/folders",
        headers=normal_user_token_headers,
        json={
            "parent_path": parent_response.json()["path"],
            "name": "Unauthorized child",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Parent folder not found"


def test_create_folder_requires_authentication(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/files/folders",
        json={"parent_path": "root", "name": "Reports"},
    )

    assert response.status_code == 401


def test_read_root_returns_root_contents(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    root_response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
    )
    root = root_response.json()
    blob_hash = "abc123"
    db.add(
        FileBlob(
            blob_hash=blob_hash,
            object_key=f"sha256/{blob_hash}",
            size_bytes=12345,
            ref_count=1,
        )
    )
    db.commit()
    child = StoredFile(
        name="report.pdf",
        owner_id=root["owner_id"],
        folder_id=root["id"],
        mime_type="application/pdf",
        category="document",
        blob_hash=blob_hash,
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
    created_entry = next(
        entry for entry in content["contents"] if entry["id"] == str(child.id)
    )
    assert created_entry["name"] == "report.pdf"
    assert created_entry["type"] == "file"
    assert created_entry["mime_type"] == "application/pdf"
    assert created_entry["category"] == "document"
    assert created_entry["blob_hash"] == "abc123"
    assert created_entry["size_bytes"] == 12345
    assert "created_at" in created_entry
    assert created_entry["created_at"] is not None
    assert isinstance(created_entry["created_at"], str)
    assert "T" in created_entry["created_at"]
    assert "owner_email" in created_entry
    assert created_entry["owner_email"] == settings.EMAIL_TEST_USER


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
        superuser_response.json()["owner_id"] != normal_user_response.json()["owner_id"]
    )


def test_read_files_by_path(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    root_response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
    )
    root = root_response.json()
    suffix = uuid.uuid4().hex
    path = f"root.documents_{suffix}"
    child_folder = Folder(
        name=f"Documents {suffix}",
        path=path,
        owner_id=root["owner_id"],
        parent_id=root["id"],
    )
    db.add(child_folder)
    db.commit()
    db.refresh(child_folder)

    response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
        params={"path": path},
    )

    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(child_folder.id)
    assert content["name"] == f"Documents {suffix}"
    assert content["path"] == path


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


@pytest.mark.parametrize(
    "path",
    [
        "",
        "root..documents",
        "root.",
        ".root",
        "root documents",
        "root.docu-ments",
        "root.documents;drop table folders",
        "root/documents",
        "root." + "a" * 1024,
    ],
)
def test_read_files_rejects_malformed_path(
    client: TestClient, normal_user_token_headers: dict[str, str], path: str
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
        params={"path": path},
    )

    assert response.status_code == 422


def test_read_files_outside_root_returns_404(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
        params={"path": "elsewhere.documents"},
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


def _create_blob_claim(
    *, db: Session, owner_id: uuid.UUID, blob_hash: str
) -> FileBlobClaim:
    claim = FileBlobClaim(owner_id=owner_id, blob_hash=blob_hash)
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def _create_pending_upload(
    *,
    db: Session,
    owner_id: uuid.UUID,
    blob_hash: str,
    object_key: str | None = None,
    size_bytes: int = 123,
    mime_type: str = "application/pdf",
) -> PendingUpload:
    upload_id = uuid.uuid4()
    pending_upload = PendingUpload(
        id=upload_id,
        owner_id=owner_id,
        blob_hash=blob_hash,
        object_key=object_key or f"uploads/{owner_id}/{upload_id}",
        size_bytes=size_bytes,
        mime_type=mime_type,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(pending_upload)
    db.commit()
    db.refresh(pending_upload)
    return pending_upload


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
    assert content["upload_required"] is True
    assert content["upload_url"] == (
        "http://localhost:9000/cloud-file-storage/sha256/upload?sig=1"
    )
    assert content["method"] == "PUT"
    assert content["headers"] == {"Content-Type": "application/pdf"}
    assert content["object_key"].startswith(f"uploads/{folder.owner_id}/")
    assert content["expires_in"] == settings.S3_PRESIGNED_URL_EXPIRES_SECONDS
    assert calls == [
        {
            "object_key": content["object_key"],
            "mime_type": "application/pdf",
        }
    ]


def test_presign_upload_existing_blob_with_claim_skips_upload(
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
    blob_hash = uuid.uuid4().hex * 2
    db.add(
        FileBlob(
            blob_hash=blob_hash,
            object_key=f"sha256/{blob_hash}",
            size_bytes=123,
            ref_count=1,
        )
    )
    db.commit()
    _create_blob_claim(db=db, owner_id=folder.owner_id, blob_hash=blob_hash)

    def fail_create_presigned_upload_url(*, object_key: str, mime_type: str) -> str:
        del object_key, mime_type
        raise AssertionError("existing blobs must not receive a PUT URL")

    monkeypatch.setattr(
        "app.files.service.storage.create_presigned_upload_url",
        fail_create_presigned_upload_url,
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/presign-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "report.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": blob_hash,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "upload_required": False,
        "upload_url": None,
        "method": None,
        "headers": {},
        "object_key": f"sha256/{blob_hash}",
        "expires_in": 0,
    }


def test_presign_upload_existing_blob_without_claim_requires_upload(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    owner_folder = _create_unique_folder(
        client=client,
        headers=superuser_token_headers,
        db=db,
        name_prefix="ExistingBlobOwner",
    )
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="ExistingBlobNoClaim",
    )
    blob_hash = uuid.uuid4().hex * 2
    db.add(
        FileBlob(
            blob_hash=blob_hash,
            object_key=f"sha256/{blob_hash}",
            size_bytes=123,
            ref_count=1,
        )
    )
    db.commit()
    _create_blob_claim(db=db, owner_id=owner_folder.owner_id, blob_hash=blob_hash)

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
            "blob_hash": blob_hash,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 200
    content = response.json()
    assert content["upload_required"] is True
    assert content["object_key"].startswith(f"uploads/{folder.owner_id}/")
    assert content["object_key"] != f"sha256/{blob_hash}"


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
    blob_hash = "f" * 64
    pending_upload = _create_pending_upload(
        db=db,
        owner_id=folder.owner_id,
        blob_hash=blob_hash,
    )
    monkeypatch.setattr(
        "app.files.service.storage.stat_object",
        lambda *, object_key: ObjectStat(
            size_bytes=123,
            content_type="application/pdf",
        ),
    )
    monkeypatch.setattr(
        "app.files.service.storage.calculate_object_sha256",
        lambda *, object_key: blob_hash,
    )
    copy_calls = []
    monkeypatch.setattr(
        "app.files.service.storage.copy_object",
        lambda *, source_object_key, destination_object_key: copy_calls.append(
            {
                "source_object_key": source_object_key,
                "destination_object_key": destination_object_key,
            }
        ),
    )
    delete_calls = []
    monkeypatch.setattr(
        "app.files.service.storage.delete_object",
        lambda *, object_key: delete_calls.append(object_key),
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "completed-report.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": blob_hash,
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
    assert content["blob_hash"] == blob_hash
    assert content["size_bytes"] == 123

    stored_file = db.exec(
        select(StoredFile).where(StoredFile.id == content["id"])
    ).first()
    assert stored_file is not None
    stored_blob = db.get(FileBlob, blob_hash)
    assert stored_blob is not None
    assert stored_blob.object_key == f"sha256/{blob_hash}"
    assert stored_blob.size_bytes == 123
    assert stored_blob.ref_count == 1
    stored_claim = db.exec(
        select(FileBlobClaim).where(
            FileBlobClaim.owner_id == folder.owner_id,
            FileBlobClaim.blob_hash == blob_hash,
        )
    ).first()
    assert stored_claim is not None
    assert copy_calls == [
        {
            "source_object_key": pending_upload.object_key,
            "destination_object_key": f"sha256/{blob_hash}",
        }
    ]
    assert delete_calls == [pending_upload.object_key]


def test_complete_upload_existing_blob_increments_ref_count(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="CompleteExistingBlob",
    )
    blob_hash = uuid.uuid4().hex * 2
    db.add(
        FileBlob(
            blob_hash=blob_hash,
            object_key=f"sha256/{blob_hash}",
            size_bytes=123,
            ref_count=1,
        )
    )
    db.commit()
    _create_blob_claim(db=db, owner_id=folder.owner_id, blob_hash=blob_hash)

    def fail_stat_object(*, object_key: str) -> ObjectStat:
        del object_key
        raise AssertionError("existing blobs should not require object stat")

    monkeypatch.setattr("app.files.service.storage.stat_object", fail_stat_object)

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "existing-blob.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": blob_hash,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 200
    db.expire_all()
    stored_blob = db.get(FileBlob, blob_hash)
    assert stored_blob is not None
    assert stored_blob.ref_count == 2


def test_complete_upload_existing_blob_without_claim_requires_pending_upload(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    owner_folder = _create_unique_folder(
        client=client,
        headers=superuser_token_headers,
        db=db,
        name_prefix="ExistingBlobClaimOwner",
    )
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="ExistingBlobClaimAttacker",
    )
    blob_hash = uuid.uuid4().hex * 2
    db.add(
        FileBlob(
            blob_hash=blob_hash,
            object_key=f"sha256/{blob_hash}",
            size_bytes=123,
            ref_count=1,
        )
    )
    db.commit()
    _create_blob_claim(db=db, owner_id=owner_folder.owner_id, blob_hash=blob_hash)

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "stolen-blob.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": blob_hash,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded object not found"
    db.expire_all()
    stored_blob = db.get(FileBlob, blob_hash)
    assert stored_blob is not None
    assert stored_blob.ref_count == 1


def test_complete_upload_existing_blob_without_claim_accepts_verified_pending_upload(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    owner_folder = _create_unique_folder(
        client=client,
        headers=superuser_token_headers,
        db=db,
        name_prefix="ExistingBlobProofOwner",
    )
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="ExistingBlobProof",
    )
    blob_hash = uuid.uuid4().hex * 2
    db.add(
        FileBlob(
            blob_hash=blob_hash,
            object_key=f"sha256/{blob_hash}",
            size_bytes=123,
            ref_count=1,
        )
    )
    db.commit()
    _create_blob_claim(db=db, owner_id=owner_folder.owner_id, blob_hash=blob_hash)
    pending_upload = _create_pending_upload(
        db=db,
        owner_id=folder.owner_id,
        blob_hash=blob_hash,
    )
    pending_upload_id = pending_upload.id
    monkeypatch.setattr(
        "app.files.service.storage.stat_object",
        lambda *, object_key: ObjectStat(
            size_bytes=123, content_type="application/pdf"
        ),
    )
    monkeypatch.setattr(
        "app.files.service.storage.calculate_object_sha256",
        lambda *, object_key: blob_hash,
    )
    copy_calls = []
    monkeypatch.setattr(
        "app.files.service.storage.copy_object",
        lambda *, source_object_key, destination_object_key: copy_calls.append(
            (source_object_key, destination_object_key)
        ),
    )
    monkeypatch.setattr(
        "app.files.service.storage.delete_object",
        lambda *, object_key: None,
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "verified-existing-blob.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": blob_hash,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 200
    db.expire_all()
    stored_blob = db.get(FileBlob, blob_hash)
    assert stored_blob is not None
    assert stored_blob.ref_count == 2
    claim = db.exec(
        select(FileBlobClaim).where(
            FileBlobClaim.owner_id == folder.owner_id,
            FileBlobClaim.blob_hash == blob_hash,
        )
    ).first()
    assert claim is not None
    assert db.get(PendingUpload, pending_upload_id) is None
    assert copy_calls == []


def test_complete_upload_recovers_when_concurrent_request_creates_blob(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="CompleteConcurrentBlob",
    )
    blob_hash = uuid.uuid4().hex * 2
    _create_pending_upload(
        db=db,
        owner_id=folder.owner_id,
        blob_hash=blob_hash,
    )
    monkeypatch.setattr(
        "app.files.service.storage.stat_object",
        lambda *, object_key: ObjectStat(size_bytes=123),
    )
    monkeypatch.setattr(
        "app.files.service.storage.calculate_object_sha256",
        lambda *, object_key: blob_hash,
    )
    monkeypatch.setattr(
        "app.files.service.storage.copy_object",
        lambda *, source_object_key, destination_object_key: None,
    )
    monkeypatch.setattr(
        "app.files.service.storage.delete_object",
        lambda *, object_key: None,
    )

    def concurrent_create_blob(
        *,
        session: Session,
        blob_hash: str,
        object_key: str,
        size_bytes: int,
        ref_count: int = 0,
    ) -> FileBlob:
        del session, ref_count
        with Session(engine) as concurrent_session:
            concurrent_session.add(
                FileBlob(
                    blob_hash=blob_hash,
                    object_key=object_key,
                    size_bytes=size_bytes,
                    ref_count=0,
                )
            )
            concurrent_session.commit()

        from app.files.repository import DuplicateFileBlobRepositoryError

        raise DuplicateFileBlobRepositoryError

    monkeypatch.setattr(
        "app.files.service.repository.create_blob", concurrent_create_blob
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "concurrent-blob.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": blob_hash,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 200
    db.expire_all()
    stored_blob = db.get(FileBlob, blob_hash)
    assert stored_blob is not None
    assert stored_blob.ref_count == 1
    stored_file = db.exec(
        select(StoredFile).where(StoredFile.id == uuid.UUID(response.json()["id"]))
    ).first()
    assert stored_file is not None


def test_complete_upload_existing_blob_size_mismatch_returns_400(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="CompleteExistingBlobSizeMismatch",
    )
    blob_hash = uuid.uuid4().hex * 2
    db.add(
        FileBlob(
            blob_hash=blob_hash,
            object_key=f"sha256/{blob_hash}",
            size_bytes=456,
            ref_count=1,
        )
    )
    db.commit()

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "existing-blob-size-mismatch.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": blob_hash,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded object size mismatch"


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
    blob_hash = "1" * 64
    _create_pending_upload(
        db=db,
        owner_id=folder.owner_id,
        blob_hash=blob_hash,
        size_bytes=456,
    )
    monkeypatch.setattr(
        "app.files.service.storage.stat_object",
        lambda *, object_key: ObjectStat(size_bytes=456),
    )
    monkeypatch.setattr(
        "app.files.service.storage.calculate_object_sha256",
        lambda *, object_key: blob_hash,
    )
    monkeypatch.setattr(
        "app.files.service.storage.copy_object",
        lambda *, source_object_key, destination_object_key: None,
    )
    monkeypatch.setattr(
        "app.files.service.storage.delete_object",
        lambda *, object_key: None,
    )

    complete_response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "listed-report.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": blob_hash,
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
    _create_pending_upload(
        db=db,
        owner_id=folder.owner_id,
        blob_hash="3" * 64,
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
    _create_pending_upload(
        db=db,
        owner_id=folder.owner_id,
        blob_hash="4" * 64,
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
    _create_pending_upload(
        db=db,
        owner_id=folder.owner_id,
        blob_hash="5" * 64,
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


def test_complete_upload_hash_mismatch_returns_400(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="CompleteUploadHashMismatch",
    )
    blob_hash = "6" * 64
    _create_pending_upload(
        db=db,
        owner_id=folder.owner_id,
        blob_hash=blob_hash,
    )
    monkeypatch.setattr(
        "app.files.service.storage.stat_object",
        lambda *, object_key: ObjectStat(
            size_bytes=123, content_type="application/pdf"
        ),
    )
    monkeypatch.setattr(
        "app.files.service.storage.calculate_object_sha256",
        lambda *, object_key: "a" * 64,
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "hash-mismatch.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": blob_hash,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded object hash mismatch"


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
    blob_hash = uuid.uuid4().hex * 2
    existing = StoredFile(
        owner_id=folder.owner_id,
        folder_id=folder.id,
        name="duplicate.pdf",
        mime_type="application/pdf",
        category="document",
        blob_hash=blob_hash,
        size_bytes=123,
    )
    db.add(
        FileBlob(
            blob_hash=blob_hash,
            object_key=f"sha256/{blob_hash}",
            size_bytes=123,
            ref_count=1,
        )
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


def test_complete_upload_duplicate_filename_does_not_increment_existing_blob(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="CompleteUploadDuplicateExistingBlob",
    )
    blob_hash = uuid.uuid4().hex * 2
    existing = StoredFile(
        owner_id=folder.owner_id,
        folder_id=folder.id,
        name="duplicate.pdf",
        mime_type="application/pdf",
        category="document",
        blob_hash=blob_hash,
        size_bytes=123,
    )
    db.add(
        FileBlob(
            blob_hash=blob_hash,
            object_key=f"sha256/{blob_hash}",
            size_bytes=123,
            ref_count=1,
        )
    )
    db.add(existing)
    db.commit()

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "duplicate.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": blob_hash,
            "size_bytes": 123,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "File name already exists"
    db.expire_all()
    blob = db.get(FileBlob, blob_hash)
    assert blob is not None
    assert blob.ref_count == 1


def test_complete_upload_repository_duplicate_conflict_returns_409(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="CompleteUploadRepositoryDuplicate",
    )
    blob_hash = "0" * 64
    _create_pending_upload(
        db=db,
        owner_id=folder.owner_id,
        blob_hash=blob_hash,
    )
    monkeypatch.setattr(
        "app.files.service.storage.stat_object",
        lambda *, object_key: ObjectStat(size_bytes=123),
    )
    monkeypatch.setattr(
        "app.files.service.storage.calculate_object_sha256",
        lambda *, object_key: blob_hash,
    )
    monkeypatch.setattr(
        "app.files.service.storage.copy_object",
        lambda *, source_object_key, destination_object_key: None,
    )
    monkeypatch.setattr(
        "app.files.service.repository.get_file_by_folder_and_name",
        lambda *, session, folder_id, name: None,
    )

    def mock_create_file(**kwargs):
        del kwargs
        from app.files.repository import DuplicateFileNameRepositoryError

        raise DuplicateFileNameRepositoryError

    monkeypatch.setattr("app.files.service.repository.create_file", mock_create_file)

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=normal_user_token_headers,
        json={
            "folder_path": folder.path,
            "name": "repository-duplicate.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": blob_hash,
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


def _create_unique_file(
    *,
    client: TestClient,
    headers: dict[str, str],
    db: Session,
    name_prefix: str = "Download",
    blob_hash: str | None = None,
) -> StoredFile:
    if blob_hash is None:
        blob_hash = uuid.uuid4().hex * 2
    folder = _create_unique_folder(
        client=client,
        headers=headers,
        db=db,
        name_prefix=name_prefix,
    )
    db.add(
        FileBlob(
            blob_hash=blob_hash,
            object_key=f"sha256/{blob_hash}",
            size_bytes=123,
            ref_count=1,
        )
    )
    db.commit()
    file = StoredFile(
        owner_id=folder.owner_id,
        folder_id=folder.id,
        name=f"{name_prefix.lower()}-{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        category="document",
        blob_hash=blob_hash,
        size_bytes=123,
    )
    db.add(file)
    db.commit()
    db.refresh(file)
    return file


def _create_child_folder(
    *,
    db: Session,
    owner_id: uuid.UUID,
    parent_id: uuid.UUID,
    parent_path: str,
    name_prefix: str,
) -> Folder:
    suffix = uuid.uuid4().hex
    folder = Folder(
        name=f"{name_prefix} {suffix}",
        path=f"{parent_path}.{name_prefix.lower()}_{suffix}",
        owner_id=owner_id,
        parent_id=parent_id,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


def _create_file_in_folder(
    *,
    db: Session,
    owner_id: uuid.UUID,
    folder_id: uuid.UUID,
    name_prefix: str,
    blob_hash: str | None = None,
    ref_count: int = 1,
) -> StoredFile:
    if blob_hash is None:
        blob_hash = uuid.uuid4().hex * 2
    if db.get(FileBlob, blob_hash) is None:
        db.add(
            FileBlob(
                blob_hash=blob_hash,
                object_key=f"sha256/{blob_hash}",
                size_bytes=123,
                ref_count=ref_count,
            )
        )
        db.commit()
    file = StoredFile(
        owner_id=owner_id,
        folder_id=folder_id,
        name=f"{name_prefix.lower()}-{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        category="document",
        blob_hash=blob_hash,
        size_bytes=123,
    )
    db.add(file)
    db.commit()
    db.refresh(file)
    return file


def test_delete_folder_succeeds_for_owner(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="DeleteFolder",
    )
    folder_id = folder.id

    response = client.delete(
        f"{settings.API_V1_STR}/files/folders/{folder_id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 204
    db.expire_all()
    assert db.get(Folder, folder_id) is None
    listing_response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
    )
    assert listing_response.status_code == 200
    assert str(folder_id) not in {
        item["id"] for item in listing_response.json()["contents"]
    }


def test_delete_folder_deletes_nested_subtree_files_and_shares(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="DeleteTree",
    )
    child_folder = _create_child_folder(
        db=db,
        owner_id=folder.owner_id,
        parent_id=folder.id,
        parent_path=folder.path,
        name_prefix="Nested",
    )
    direct_file = _create_file_in_folder(
        db=db,
        owner_id=folder.owner_id,
        folder_id=folder.id,
        name_prefix="Direct",
    )
    nested_file = _create_file_in_folder(
        db=db,
        owner_id=folder.owner_id,
        folder_id=child_folder.id,
        name_prefix="Nested",
    )
    folder_id = folder.id
    child_folder_id = child_folder.id
    direct_file_id = direct_file.id
    direct_file_blob_hash = direct_file.blob_hash
    nested_file_id = nested_file.id
    nested_file_blob_hash = nested_file.blob_hash
    share_response = client.post(
        f"{settings.API_V1_STR}/files/{nested_file.id}/shares",
        headers=normal_user_token_headers,
        json={"recipient_email": settings.FIRST_SUPERUSER},
    )
    assert share_response.status_code == 201
    deleted_object_keys: list[str] = []
    monkeypatch.setattr(
        "app.files.service.storage.delete_object",
        lambda *, object_key: deleted_object_keys.append(object_key),
    )

    response = client.delete(
        f"{settings.API_V1_STR}/files/folders/{folder_id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 204
    db.expire_all()
    assert db.get(Folder, folder_id) is None
    assert db.get(Folder, child_folder_id) is None
    assert db.get(StoredFile, direct_file_id) is None
    assert db.get(StoredFile, nested_file_id) is None
    assert (
        db.exec(select(FileShare).where(FileShare.file_id == nested_file_id)).first()
        is None
    )
    assert db.get(FileBlob, direct_file_blob_hash) is None
    assert db.get(FileBlob, nested_file_blob_hash) is None
    assert sorted(deleted_object_keys) == sorted(
        [
            f"sha256/{direct_file_blob_hash}",
            f"sha256/{nested_file_blob_hash}",
        ]
    )

    shared_response = client.get(
        f"{settings.API_V1_STR}/files/shared-with-me",
        headers=superuser_token_headers,
    )
    assert shared_response.status_code == 200
    assert str(nested_file_id) not in {
        item["id"] for item in shared_response.json()["data"]
    }
    download_response = client.post(
        f"{settings.API_V1_STR}/files/{nested_file_id}/presign-download",
        headers=normal_user_token_headers,
    )
    assert download_response.status_code == 404


def test_delete_folder_rejects_another_users_folder(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=superuser_token_headers,
        db=db,
        name_prefix="OtherDeleteFolder",
    )

    response = client.delete(
        f"{settings.API_V1_STR}/files/folders/{folder.id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Folder not found"
    assert db.get(Folder, folder.id) is not None


def test_delete_folder_rejects_root(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    root_response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
    )
    assert root_response.status_code == 200
    root_id = root_response.json()["id"]

    response = client.delete(
        f"{settings.API_V1_STR}/files/folders/{root_id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Folder not found"
    assert db.get(Folder, uuid.UUID(root_id)) is not None


def test_delete_folder_repeated_delete_returns_404(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="RepeatedDeleteFolder",
    )

    first_response = client.delete(
        f"{settings.API_V1_STR}/files/folders/{folder.id}",
        headers=normal_user_token_headers,
    )
    second_response = client.delete(
        f"{settings.API_V1_STR}/files/folders/{folder.id}",
        headers=normal_user_token_headers,
    )

    assert first_response.status_code == 204
    assert second_response.status_code == 404
    assert second_response.json()["detail"] == "Folder not found"


def test_delete_folder_requires_authentication(client: TestClient) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/files/folders/{uuid.uuid4()}",
    )

    assert response.status_code == 401


def test_delete_folder_invalid_uuid_returns_422(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/files/folders/not-a-uuid",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 422


def test_delete_folder_blob_integrity_error_returns_409(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    monkeypatch,
) -> None:
    def raise_blob_integrity_error(**kwargs) -> None:
        del kwargs
        raise BlobIntegrityError("File blob metadata is missing")

    monkeypatch.setattr(
        "app.api.routes.files.delete_folder",
        raise_blob_integrity_error,
    )

    response = client.delete(
        f"{settings.API_V1_STR}/files/folders/{uuid.uuid4()}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "File blob metadata is inconsistent"


def test_delete_folder_shared_blob_decrements_ref_count_without_s3_delete(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="SharedBlobFolder",
    )
    outside_folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="OutsideSharedBlobFolder",
    )
    blob_hash = uuid.uuid4().hex * 2
    inside_file = _create_file_in_folder(
        db=db,
        owner_id=folder.owner_id,
        folder_id=folder.id,
        name_prefix="InsideSharedBlob",
        blob_hash=blob_hash,
        ref_count=2,
    )
    outside_file = _create_file_in_folder(
        db=db,
        owner_id=folder.owner_id,
        folder_id=outside_folder.id,
        name_prefix="OutsideSharedBlob",
        blob_hash=blob_hash,
    )
    folder_id = folder.id
    inside_file_id = inside_file.id
    outside_file_id = outside_file.id
    blob = db.get(FileBlob, blob_hash)
    assert blob is not None
    blob.ref_count = 2
    db.add(blob)
    db.commit()

    def fail_delete_object(*, object_key: str) -> None:
        del object_key
        raise AssertionError("shared blob object must not be deleted")

    monkeypatch.setattr("app.files.service.storage.delete_object", fail_delete_object)

    response = client.delete(
        f"{settings.API_V1_STR}/files/folders/{folder_id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 204
    db.expire_all()
    assert db.get(StoredFile, inside_file_id) is None
    assert db.get(StoredFile, outside_file_id) is not None
    stored_blob = db.get(FileBlob, blob_hash)
    assert stored_blob is not None
    assert stored_blob.ref_count == 1


def test_delete_folder_s3_delete_failure_does_not_restore_db_rows(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
    caplog,
) -> None:
    folder = _create_unique_folder(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="DeleteFolderS3Failure",
    )
    file = _create_file_in_folder(
        db=db,
        owner_id=folder.owner_id,
        folder_id=folder.id,
        name_prefix="DeleteFolderS3Failure",
    )
    folder_id = folder.id
    file_id = file.id
    blob_hash = file.blob_hash

    def fail_delete_object(*, object_key: str) -> None:
        del object_key
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr("app.files.service.storage.delete_object", fail_delete_object)

    response = client.delete(
        f"{settings.API_V1_STR}/files/folders/{folder_id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 204
    db.expire_all()
    assert db.get(Folder, folder_id) is None
    assert db.get(StoredFile, file_id) is None
    assert db.get(FileBlob, blob_hash) is None
    assert "Failed to delete unreferenced folder blob object" in caplog.text


def test_presign_download_succeeds_for_owned_file(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="Download",
        blob_hash="a" * 64,
    )
    calls = []

    def mock_create_presigned_download_url(*, object_key: str, filename: str) -> str:
        calls.append({"object_key": object_key, "filename": filename})
        return "http://localhost:9000/cloud-file-storage/sha256/download?sig=1"

    monkeypatch.setattr(
        "app.files.service.storage.create_presigned_download_url",
        mock_create_presigned_download_url,
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/{file.id}/presign-download",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "download_url": "http://localhost:9000/cloud-file-storage/sha256/download?sig=1",
        "method": "GET",
        "expires_in": settings.S3_PRESIGNED_URL_EXPIRES_SECONDS,
    }
    assert calls == [{"object_key": f"sha256/{'a' * 64}", "filename": file.name}]


def test_presign_download_missing_file_returns_404(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/files/{uuid.uuid4()}/presign-download",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "File not found"


def test_presign_download_rejects_another_users_file(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=superuser_token_headers,
        db=db,
        name_prefix="DownloadSuper",
        blob_hash="b" * 64,
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/{file.id}/presign-download",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "File not found"


def test_presign_download_invalid_uuid_returns_422(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/files/not-a-uuid/presign-download",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 422


def test_presign_download_requires_authentication(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/files/{uuid.uuid4()}/presign-download",
    )

    assert response.status_code == 401


def test_delete_file_succeeds_for_owner(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="Delete",
    )
    calls = []
    monkeypatch.setattr(
        "app.files.service.storage.delete_object",
        lambda *, object_key: calls.append(object_key),
    )
    file_id = file.id
    blob_hash = file.blob_hash

    response = client.delete(
        f"{settings.API_V1_STR}/files/{file_id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 204
    assert response.content == b""
    db.expire_all()
    assert db.get(StoredFile, file_id) is None
    assert db.get(FileBlob, blob_hash) is None
    assert calls == [f"sha256/{blob_hash}"]


def test_delete_file_removes_file_from_folder_listing(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="DeleteListing",
    )
    folder = db.get(Folder, file.folder_id)
    assert folder is not None
    monkeypatch.setattr(
        "app.files.service.storage.delete_object",
        lambda *, object_key: None,
    )

    response = client.delete(
        f"{settings.API_V1_STR}/files/{file.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 204

    listing_response = client.get(
        f"{settings.API_V1_STR}/files",
        headers=normal_user_token_headers,
        params={"path": folder.path},
    )
    assert listing_response.status_code == 200
    assert all(
        item["id"] != str(file.id) for item in listing_response.json()["contents"]
    )


def test_delete_file_prevents_later_download(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="DeleteDownload",
    )
    monkeypatch.setattr(
        "app.files.service.storage.delete_object",
        lambda *, object_key: None,
    )

    delete_response = client.delete(
        f"{settings.API_V1_STR}/files/{file.id}",
        headers=normal_user_token_headers,
    )
    assert delete_response.status_code == 204

    download_response = client.post(
        f"{settings.API_V1_STR}/files/{file.id}/presign-download",
        headers=normal_user_token_headers,
    )
    assert download_response.status_code == 404
    assert download_response.json()["detail"] == "File not found"


def test_delete_file_removes_shares(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="DeleteShared",
    )
    share_response = client.post(
        f"{settings.API_V1_STR}/files/{file.id}/shares",
        headers=normal_user_token_headers,
        json={"recipient_email": settings.FIRST_SUPERUSER},
    )
    assert share_response.status_code == 201
    monkeypatch.setattr(
        "app.files.service.storage.delete_object",
        lambda *, object_key: None,
    )

    delete_response = client.delete(
        f"{settings.API_V1_STR}/files/{file.id}",
        headers=normal_user_token_headers,
    )
    assert delete_response.status_code == 204

    recipient_listing = client.get(
        f"{settings.API_V1_STR}/files/shared-with-me",
        headers=superuser_token_headers,
    )
    assert recipient_listing.status_code == 200
    assert all(item["id"] != str(file.id) for item in recipient_listing.json()["data"])

    download_response = client.post(
        f"{settings.API_V1_STR}/files/{file.id}/presign-download",
        headers=superuser_token_headers,
    )
    assert download_response.status_code == 404


def test_delete_file_rejects_another_users_file(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=superuser_token_headers,
        db=db,
        name_prefix="DeleteOtherUser",
    )

    response = client.delete(
        f"{settings.API_V1_STR}/files/{file.id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "File not found"
    assert db.get(StoredFile, file.id) is not None


def test_delete_file_rejects_shared_recipient(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="DeleteRecipient",
    )
    share_response = client.post(
        f"{settings.API_V1_STR}/files/{file.id}/shares",
        headers=normal_user_token_headers,
        json={"recipient_email": settings.FIRST_SUPERUSER},
    )
    assert share_response.status_code == 201

    response = client.delete(
        f"{settings.API_V1_STR}/files/{file.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "File not found"
    assert db.get(StoredFile, file.id) is not None


def test_delete_file_repeated_delete_returns_404(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="DeleteRepeated",
    )
    monkeypatch.setattr(
        "app.files.service.storage.delete_object",
        lambda *, object_key: None,
    )

    first_response = client.delete(
        f"{settings.API_V1_STR}/files/{file.id}",
        headers=normal_user_token_headers,
    )
    second_response = client.delete(
        f"{settings.API_V1_STR}/files/{file.id}",
        headers=normal_user_token_headers,
    )

    assert first_response.status_code == 204
    assert second_response.status_code == 404
    assert second_response.json()["detail"] == "File not found"


def test_delete_file_requires_authentication(client: TestClient) -> None:
    response = client.delete(f"{settings.API_V1_STR}/files/{uuid.uuid4()}")

    assert response.status_code == 401


def test_delete_file_invalid_uuid_returns_422(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/files/not-a-uuid",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 422


def test_delete_file_shared_blob_decrements_ref_count_without_s3_delete(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    blob_hash = uuid.uuid4().hex * 2
    first_file = _create_unique_file(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="DeleteSharedBlobA",
        blob_hash=blob_hash,
    )
    second_file = StoredFile(
        owner_id=first_file.owner_id,
        folder_id=first_file.folder_id,
        name=f"shared-blob-{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        category="document",
        blob_hash=blob_hash,
        size_bytes=123,
    )
    blob = db.get(FileBlob, blob_hash)
    assert blob is not None
    blob.ref_count = 2
    db.add(second_file)
    db.add(blob)
    db.commit()
    db.refresh(second_file)

    def fail_delete_object(*, object_key: str) -> None:
        del object_key
        raise AssertionError("shared blob object must not be deleted")

    monkeypatch.setattr("app.files.service.storage.delete_object", fail_delete_object)
    first_file_id = first_file.id
    second_file_id = second_file.id

    response = client.delete(
        f"{settings.API_V1_STR}/files/{first_file_id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 204
    db.expire_all()
    assert db.get(StoredFile, first_file_id) is None
    assert db.get(StoredFile, second_file_id) is not None
    stored_blob = db.get(FileBlob, blob_hash)
    assert stored_blob is not None
    assert stored_blob.ref_count == 1


def test_delete_file_final_blob_reference_deletes_blob_and_s3_object(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="DeleteFinalBlob",
    )
    calls = []
    monkeypatch.setattr(
        "app.files.service.storage.delete_object",
        lambda *, object_key: calls.append(object_key),
    )
    file_id = file.id
    blob_hash = file.blob_hash

    response = client.delete(
        f"{settings.API_V1_STR}/files/{file_id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 204
    db.expire_all()
    assert db.get(StoredFile, file_id) is None
    assert db.get(FileBlob, blob_hash) is None
    assert calls == [f"sha256/{blob_hash}"]


def test_delete_file_s3_delete_failure_does_not_restore_file(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="DeleteS3Failure",
    )

    def fail_delete_object(*, object_key: str) -> None:
        del object_key
        raise RuntimeError("S3 unavailable")

    monkeypatch.setattr("app.files.service.storage.delete_object", fail_delete_object)
    file_id = file.id
    blob_hash = file.blob_hash

    response = client.delete(
        f"{settings.API_V1_STR}/files/{file_id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 204
    db.expire_all()
    assert db.get(StoredFile, file_id) is None
    assert db.get(FileBlob, blob_hash) is None


def test_share_file_lists_for_recipient_and_allows_download(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="Shared",
        blob_hash="c" * 64,
    )
    share_response = client.post(
        f"{settings.API_V1_STR}/files/{file.id}/shares",
        headers=normal_user_token_headers,
        json={"recipient_email": settings.FIRST_SUPERUSER},
    )

    assert share_response.status_code == 201
    share = share_response.json()
    assert share["file_id"] == str(file.id)
    assert share["recipient_email"] == settings.FIRST_SUPERUSER

    listing_response = client.get(
        f"{settings.API_V1_STR}/files/shared-with-me",
        headers=superuser_token_headers,
    )
    assert listing_response.status_code == 200
    listing = listing_response.json()
    shared_file = next(item for item in listing["data"] if item["id"] == str(file.id))
    assert shared_file == {
        "id": str(file.id),
        "name": file.name,
        "mime_type": file.mime_type,
        "category": file.category,
        "size_bytes": file.size_bytes,
        "owner_email": settings.EMAIL_TEST_USER,
        "shared_at": share["created_at"],
    }
    assert listing["count"] == len(listing["data"])
    assert "blob_hash" not in shared_file

    monkeypatch.setattr(
        "app.files.service.storage.create_presigned_download_url",
        lambda *, object_key, filename: "http://localhost/shared-download",
    )
    download_response = client.post(
        f"{settings.API_V1_STR}/files/{file.id}/presign-download",
        headers=superuser_token_headers,
    )
    assert download_response.status_code == 200
    assert (
        download_response.json()["download_url"] == "http://localhost/shared-download"
    )


def test_share_file_rejects_duplicate_recipient(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="DuplicateShare",
    )
    url = f"{settings.API_V1_STR}/files/{file.id}/shares"
    payload = {"recipient_email": settings.FIRST_SUPERUSER}

    assert (
        client.post(url, headers=normal_user_token_headers, json=payload).status_code
        == 201
    )
    response = client.post(url, headers=normal_user_token_headers, json=payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "File is already shared with this recipient"


def test_share_file_rejects_self_unknown_and_inactive_recipients(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="InvalidShare",
    )
    url = f"{settings.API_V1_STR}/files/{file.id}/shares"

    self_response = client.post(
        url,
        headers=normal_user_token_headers,
        json={"recipient_email": settings.EMAIL_TEST_USER},
    )
    assert self_response.status_code == 422

    missing_response = client.post(
        url,
        headers=normal_user_token_headers,
        json={"recipient_email": random_email()},
    )
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "Recipient not found"

    inactive_email = random_email()
    inactive = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=inactive_email,
            password="inactive-password",
            is_active=False,
        ),
    )
    assert inactive.is_active is False
    inactive_response = client.post(
        url,
        headers=normal_user_token_headers,
        json={"recipient_email": inactive_email},
    )
    assert inactive_response.status_code == 422
    assert inactive_response.json()["detail"] == "Recipient is inactive"


def test_share_file_rejects_non_owner_and_requires_authentication(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=superuser_token_headers,
        db=db,
        name_prefix="PrivateShare",
    )
    url = f"{settings.API_V1_STR}/files/{file.id}/shares"
    payload = {"recipient_email": settings.FIRST_SUPERUSER}

    response = client.post(url, headers=normal_user_token_headers, json=payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "File not found"
    assert client.post(url, json=payload).status_code == 401


def test_shared_with_me_requires_authentication(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/files/shared-with-me")

    assert response.status_code == 401


def test_shared_with_me_is_empty_for_user_without_shares(
    client: TestClient,
    db: Session,
) -> None:
    email = random_email()
    headers = authentication_token_from_email(client=client, email=email, db=db)

    response = client.get(
        f"{settings.API_V1_STR}/files/shared-with-me",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {"data": [], "count": 0}


def test_owner_lists_and_revokes_file_share(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="ManagedShare",
    )
    shares_url = f"{settings.API_V1_STR}/files/{file.id}/shares"
    create_response = client.post(
        shares_url,
        headers=normal_user_token_headers,
        json={"recipient_email": settings.FIRST_SUPERUSER},
    )
    assert create_response.status_code == 201
    share = create_response.json()

    list_response = client.get(shares_url, headers=normal_user_token_headers)
    assert list_response.status_code == 200
    assert list_response.json() == {"data": [share], "count": 1}

    revoke_url = f"{shares_url}/{share['id']}"
    revoke_response = client.delete(
        revoke_url,
        headers=normal_user_token_headers,
    )
    assert revoke_response.status_code == 204
    assert revoke_response.content == b""

    recipient_listing = client.get(
        f"{settings.API_V1_STR}/files/shared-with-me",
        headers=superuser_token_headers,
    )
    assert recipient_listing.status_code == 200
    assert all(item["id"] != str(file.id) for item in recipient_listing.json()["data"])

    download_response = client.post(
        f"{settings.API_V1_STR}/files/{file.id}/presign-download",
        headers=superuser_token_headers,
    )
    assert download_response.status_code == 404

    repeated_response = client.delete(
        revoke_url,
        headers=normal_user_token_headers,
    )
    assert repeated_response.status_code == 404
    assert repeated_response.json()["detail"] == "File share not found"


def test_share_management_is_owner_scoped_and_requires_authentication(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    file = _create_unique_file(
        client=client,
        headers=normal_user_token_headers,
        db=db,
        name_prefix="PrivateManagedShare",
    )
    shares_url = f"{settings.API_V1_STR}/files/{file.id}/shares"
    share_response = client.post(
        shares_url,
        headers=normal_user_token_headers,
        json={"recipient_email": settings.FIRST_SUPERUSER},
    )
    assert share_response.status_code == 201
    revoke_url = f"{shares_url}/{share_response.json()['id']}"

    list_response = client.get(shares_url, headers=superuser_token_headers)
    assert list_response.status_code == 404
    assert list_response.json()["detail"] == "File not found"
    revoke_response = client.delete(revoke_url, headers=superuser_token_headers)
    assert revoke_response.status_code == 404
    assert revoke_response.json()["detail"] == "File not found"

    owner_listing = client.get(shares_url, headers=normal_user_token_headers)
    assert owner_listing.status_code == 200
    assert owner_listing.json()["count"] == 1
    assert owner_listing.json()["data"][0]["id"] == share_response.json()["id"]

    assert client.get(shares_url).status_code == 401
    assert client.delete(revoke_url).status_code == 401
