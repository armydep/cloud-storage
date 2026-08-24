import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Lock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.core.db import engine
from app.core.storage import ObjectStat, sha256_hex_to_base64
from app.files import repository as files_repository
from app.files import service as files_service
from app.files.models import FileBlob, PendingUpload, StoredFile
from app.files.schemas import PresignUploadRequest
from app.models import User, UserCreate
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


def _create_user_and_headers(
    *, client: TestClient, db: Session
) -> tuple[dict[str, str], User]:
    email = random_email()
    password = random_lower_string()
    user = crud.create_user(
        session=db, user_create=UserCreate(email=email, password=password)
    )
    headers = user_authentication_headers(client=client, email=email, password=password)
    return headers, user


def _root_folder(*, client: TestClient, headers: dict[str, str]) -> dict:
    return client.get(f"{settings.API_V1_STR}/files", headers=headers).json()


def _set_quota_bytes(*, db: Session, user: User, quota_bytes: int | None) -> None:
    user.quota_bytes = quota_bytes
    db.add(user)
    db.commit()


def test_quota_usage_defaults_to_the_configured_default_with_zero_usage(
    client: TestClient, db: Session
) -> None:
    headers, _user = _create_user_and_headers(client=client, db=db)

    response = client.get(f"{settings.API_V1_STR}/files/quota", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "used_bytes": 0,
        "total_bytes": settings.QUOTA_DEFAULT_BYTES,
    }


def test_quota_usage_reflects_a_per_user_override(
    client: TestClient, db: Session
) -> None:
    headers, user = _create_user_and_headers(client=client, db=db)
    _set_quota_bytes(db=db, user=user, quota_bytes=12345)

    response = client.get(f"{settings.API_V1_STR}/files/quota", headers=headers)

    assert response.json()["total_bytes"] == 12345


def test_quota_usage_requires_authentication(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/files/quota")

    assert response.status_code == 401


def test_presign_upload_rejected_when_it_would_exceed_quota(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user = _create_user_and_headers(client=client, db=db)
    root = _root_folder(client=client, headers=headers)
    _set_quota_bytes(db=db, user=user, quota_bytes=100)

    def fail_create_presigned_upload_url(
        *, object_key: str, mime_type: str, checksum_sha256: str
    ) -> str:
        del object_key, mime_type, checksum_sha256
        raise AssertionError("must not presign an upload rejected for quota")

    monkeypatch.setattr(
        "app.files.service.storage.create_presigned_upload_url",
        fail_create_presigned_upload_url,
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/presign-upload",
        headers=headers,
        json={
            "folder_path": root["path"],
            "name": "big.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": uuid.uuid4().hex * 2,
            "size_bytes": 200,
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Storage quota exceeded"
    pending = db.exec(
        select(PendingUpload).where(PendingUpload.owner_id == user.id)
    ).all()
    assert pending == []


def test_presign_upload_succeeds_within_quota(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user = _create_user_and_headers(client=client, db=db)
    root = _root_folder(client=client, headers=headers)
    _set_quota_bytes(db=db, user=user, quota_bytes=1000)
    monkeypatch.setattr(
        "app.files.service.storage.create_presigned_upload_url",
        lambda *, object_key, mime_type, checksum_sha256: "https://example.com/put",
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/presign-upload",
        headers=headers,
        json={
            "folder_path": root["path"],
            "name": "small.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": uuid.uuid4().hex * 2,
            "size_bytes": 200,
        },
    )

    assert response.status_code == 200
    assert response.json()["upload_required"] is True


def test_complete_upload_rejected_when_verified_size_would_exceed_quota(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The completion check is authoritative (decisions 5 and 7): even

    though nothing here forced presign to under-report, this proves
    completion enforces quota independently using the verified size, and
    that rejection deletes the pending object (decision 6).
    """
    headers, user = _create_user_and_headers(client=client, db=db)
    root = _root_folder(client=client, headers=headers)
    blob_hash = uuid.uuid4().hex * 2
    pending_upload = files_repository.create_pending_upload(
        session=db,
        upload_id=uuid.uuid4(),
        owner_id=user.id,
        blob_hash=blob_hash,
        object_key=f"uploads/{user.id}/{uuid.uuid4()}",
        size_bytes=200,
        mime_type="application/pdf",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.commit()
    _set_quota_bytes(db=db, user=user, quota_bytes=100)

    monkeypatch.setattr(
        "app.files.service.storage.stat_object",
        lambda *, object_key, include_checksum=False: ObjectStat(
            size_bytes=200,
            content_type="application/pdf",
            checksum_sha256=sha256_hex_to_base64(blob_hash),
        ),
    )
    delete_calls = []
    monkeypatch.setattr(
        "app.files.service.storage.delete_object",
        lambda *, object_key: delete_calls.append(object_key),
    )

    response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=headers,
        json={
            "folder_path": root["path"],
            "name": "big.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": blob_hash,
            "size_bytes": 200,
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Storage quota exceeded"
    assert delete_calls == [pending_upload.object_key]
    assert (
        db.exec(select(StoredFile).where(StoredFile.owner_id == user.id)).first()
        is None
    )
    assert db.get(FileBlob, blob_hash) is None


def test_lowering_quota_below_current_usage_leaves_files_intact(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user = _create_user_and_headers(client=client, db=db)
    root = _root_folder(client=client, headers=headers)
    blob_hash = uuid.uuid4().hex * 2
    files_repository.create_pending_upload(
        session=db,
        upload_id=uuid.uuid4(),
        owner_id=user.id,
        blob_hash=blob_hash,
        object_key=f"uploads/{user.id}/{uuid.uuid4()}",
        size_bytes=800,
        mime_type="application/pdf",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.commit()
    monkeypatch.setattr(
        "app.files.service.storage.stat_object",
        lambda *, object_key, include_checksum=False: ObjectStat(
            size_bytes=800,
            content_type="application/pdf",
            checksum_sha256=sha256_hex_to_base64(blob_hash),
        ),
    )
    monkeypatch.setattr(
        "app.files.service.storage.copy_object",
        lambda *, source_object_key, destination_object_key: None,
    )
    monkeypatch.setattr(
        "app.files.service.storage.delete_object", lambda *, object_key: None
    )
    complete_response = client.post(
        f"{settings.API_V1_STR}/files/complete-upload",
        headers=headers,
        json={
            "folder_path": root["path"],
            "name": "existing.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": blob_hash,
            "size_bytes": 800,
        },
    )
    assert complete_response.status_code == 200
    file_id = complete_response.json()["id"]

    # Now lower the quota below the 800 bytes already used.
    _set_quota_bytes(db=db, user=user, quota_bytes=100)

    # The existing file is untouched and still downloadable/listed.
    listing = client.get(
        f"{settings.API_V1_STR}/files",
        headers=headers,
        params={"path": root["path"]},
    )
    assert listing.status_code == 200
    assert any(item["id"] == file_id for item in listing.json()["contents"])
    download_response = client.post(
        f"{settings.API_V1_STR}/files/{file_id}/presign-download",
        headers=headers,
    )
    assert download_response.status_code == 200

    # A new upload is blocked until usage drops back under the new quota.
    new_response = client.post(
        f"{settings.API_V1_STR}/files/presign-upload",
        headers=headers,
        json={
            "folder_path": root["path"],
            "name": "new.pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "blob_hash": uuid.uuid4().hex * 2,
            "size_bytes": 50,
        },
    )
    assert new_response.status_code == 413

    # Deleting still works while over quota (decision 4).
    delete_response = client.delete(
        f"{settings.API_V1_STR}/files/{file_id}", headers=headers
    )
    assert delete_response.status_code == 204


def _synchronize_user_locks(
    *, monkeypatch: pytest.MonkeyPatch, expected_calls: int
) -> None:
    """Force N concurrent callers of `get_user_for_update` to all arrive

    at the row lock before any of them proceeds, maximizing the chance a
    genuine read-then-write race would be exercised if the lock were
    absent -- mirrors `_synchronize_first_blob_locks` in test_files.py,
    applied to the user-row lock quota enforcement relies on instead.
    """
    original = files_repository.get_user_for_update
    barrier = Barrier(expected_calls)
    lock = Lock()
    call_count = 0

    def synchronized(*, session: Session, user_id: uuid.UUID) -> User | None:
        nonlocal call_count
        should_wait = False
        with lock:
            if call_count < expected_calls:
                call_count += 1
                should_wait = True
        if should_wait:
            barrier.wait(timeout=10)
        return original(session=session, user_id=user_id)

    monkeypatch.setattr(
        "app.files.service.repository.get_user_for_update", synchronized
    )


def test_two_concurrent_uploads_from_the_same_user_cannot_jointly_exceed_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = random_email()
    password = random_lower_string()
    with Session(engine) as setup_session:
        user = crud.create_user(
            session=setup_session,
            user_create=UserCreate(email=email, password=password),
        )
        user.quota_bytes = 100
        setup_session.add(user)
        setup_session.commit()
        setup_session.refresh(user)
        root = files_repository.create_root_folder(
            session=setup_session, owner_id=user.id
        )
        user_id = user.id
        folder_path = root.path

    monkeypatch.setattr(
        "app.files.service.storage.create_presigned_upload_url",
        lambda *, object_key, mime_type, checksum_sha256: "https://example.com/put",
    )
    _synchronize_user_locks(monkeypatch=monkeypatch, expected_calls=2)

    def presign(blob_hash: str) -> object:
        try:
            with Session(engine) as session:
                return files_service.create_presigned_upload(
                    session=session,
                    owner_id=user_id,
                    request=PresignUploadRequest(
                        folder_path=folder_path,
                        name=f"{blob_hash[:8]}.pdf",
                        mime_type="application/pdf",
                        category="document",
                        blob_hash=blob_hash,
                        size_bytes=60,
                    ),
                )
        except files_service.QuotaExceededError as exc:
            return exc

    blob_a = uuid.uuid4().hex * 2
    blob_b = uuid.uuid4().hex * 2

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(presign, blob_a)
        second = executor.submit(presign, blob_b)
        first_result = first.result(timeout=10)
        second_result = second.result(timeout=10)

    results = [first_result, second_result]
    successes = [
        r for r in results if isinstance(r, files_service.PresignUploadResponse)
    ]
    failures = [r for r in results if isinstance(r, files_service.QuotaExceededError)]
    assert len(successes) == 1
    assert len(failures) == 1

    with Session(engine) as check_session:
        usage = files_repository.get_usage_bytes(
            session=check_session, owner_id=user_id
        )
    assert usage == 60
