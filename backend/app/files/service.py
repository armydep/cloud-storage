import logging
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlmodel import Session

from app.core import storage
from app.core.config import settings
from app.files import repository
from app.files.repository import ROOT_FOLDER_PATH
from app.files.schemas import (
    CompleteUploadRequest,
    FileShareCreate,
    FileSharePublic,
    FileSharesPublic,
    FolderContentPublic,
    FolderCreate,
    FolderPublic,
    FolderWithContentsPublic,
    PresignDownloadResponse,
    PresignUploadRequest,
    PresignUploadResponse,
    SharedFilePublic,
    SharedFilesPublic,
    StoredFilePublic,
)

logger = logging.getLogger(__name__)


class FolderNotFoundError(Exception):
    pass


class StoredFileNotFoundError(Exception):
    pass


class ObjectNotUploadedError(Exception):
    pass


class ObjectSizeMismatchError(Exception):
    pass


class ObjectContentTypeMismatchError(Exception):
    pass


class ObjectHashMismatchError(Exception):
    pass


class DuplicateFileNameError(Exception):
    pass


class DuplicateFolderNameError(Exception):
    pass


class InvalidFolderNameError(Exception):
    pass


class ShareRecipientNotFoundError(Exception):
    pass


class ShareRecipientInactiveError(Exception):
    pass


class CannotShareWithOwnerError(Exception):
    pass


class DuplicateFileShareError(Exception):
    pass


class FileShareNotFoundError(Exception):
    pass


class BlobIntegrityError(Exception):
    pass


def _folder_path_segment(name: str) -> str:
    segment = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")
    if not segment:
        raise InvalidFolderNameError
    if segment[0].isdigit():
        segment = f"_{segment}"
    return segment


def create_folder(
    *, session: Session, owner_id: uuid.UUID, request: FolderCreate
) -> FolderPublic:
    parent = repository.get_folder_by_path(
        session=session,
        owner_id=owner_id,
        path=request.parent_path,
    )
    if not parent and request.parent_path == ROOT_FOLDER_PATH:
        parent = repository.create_root_folder(session=session, owner_id=owner_id)
    if not parent:
        raise FolderNotFoundError

    path = f"{parent.path}.{_folder_path_segment(request.name)}"
    if len(path) > 1024:
        raise InvalidFolderNameError

    try:
        folder = repository.create_folder(
            session=session,
            owner_id=owner_id,
            parent_id=parent.id,
            name=request.name,
            path=path,
        )
    except repository.DuplicateFolderRepositoryError:
        raise DuplicateFolderNameError
    return FolderPublic.model_validate(folder)


def get_folder_contents(
    *, session: Session, owner_id: uuid.UUID, path: str
) -> FolderWithContentsPublic:
    folder = repository.get_folder_by_path(
        session=session,
        owner_id=owner_id,
        path=path,
    )
    if not folder and path == ROOT_FOLDER_PATH:
        folder = repository.create_root_folder(session=session, owner_id=owner_id)

    if not folder:
        raise FolderNotFoundError

    child_folders = repository.list_child_folders(
        session=session,
        owner_id=owner_id,
        parent_id=folder.id,
    )
    files_with_owner = repository.list_folder_files_with_owner(
        session=session,
        owner_id=owner_id,
        folder_id=folder.id,
    )
    contents = [
        FolderContentPublic(
            id=child_folder.id,
            name=child_folder.name,
            type="folder",
            path=child_folder.path,
        )
        for child_folder in child_folders
    ] + [
        FolderContentPublic(
            id=file.id,
            name=file.name,
            type="file",
            mime_type=file.mime_type,
            category=file.category,
            blob_hash=file.blob_hash,
            size_bytes=file.size_bytes,
            created_at=file.created_at,
            owner_email=owner_email,
        )
        for file, owner_email in files_with_owner
    ]

    return FolderWithContentsPublic.model_validate(
        folder, update={"contents": contents}
    )


def create_presigned_upload(
    *, session: Session, owner_id: uuid.UUID, request: PresignUploadRequest
) -> PresignUploadResponse:
    folder = repository.get_folder_by_path(
        session=session,
        owner_id=owner_id,
        path=request.folder_path,
    )
    if not folder:
        raise FolderNotFoundError

    existing_blob = repository.get_blob_by_hash(
        session=session,
        blob_hash=request.blob_hash,
    )
    existing_claim = repository.get_blob_claim(
        session=session,
        owner_id=owner_id,
        blob_hash=request.blob_hash,
    )
    if existing_blob and existing_claim:
        return PresignUploadResponse(
            upload_required=False,
            upload_url=None,
            method=None,
            headers={},
            object_key=existing_blob.object_key,
            expires_in=0,
        )

    upload_id = uuid.uuid4()
    object_key = storage.get_pending_upload_object_key(
        owner_id=owner_id,
        upload_id=upload_id,
    )
    upload_url = storage.create_presigned_upload_url(
        object_key=object_key,
        mime_type=request.mime_type,
        checksum_sha256=storage.sha256_hex_to_base64(request.blob_hash),
    )
    repository.create_pending_upload(
        session=session,
        upload_id=upload_id,
        owner_id=owner_id,
        blob_hash=request.blob_hash,
        object_key=object_key,
        size_bytes=request.size_bytes,
        mime_type=request.mime_type,
        expires_at=datetime.now(timezone.utc)
        + timedelta(seconds=settings.S3_PRESIGNED_URL_EXPIRES_SECONDS),
    )
    session.commit()

    return PresignUploadResponse(
        upload_required=True,
        upload_url=upload_url,
        headers={
            "Content-Type": request.mime_type,
            "x-amz-checksum-sha256": storage.sha256_hex_to_base64(request.blob_hash),
        },
        object_key=object_key,
        expires_in=settings.S3_PRESIGNED_URL_EXPIRES_SECONDS,
    )


def complete_upload(
    *, session: Session, owner_id: uuid.UUID, request: CompleteUploadRequest
) -> StoredFilePublic:
    folder = repository.get_folder_by_path(
        session=session,
        owner_id=owner_id,
        path=request.folder_path,
    )
    if not folder:
        raise FolderNotFoundError

    existing_file = repository.get_file_by_folder_and_name(
        session=session,
        folder_id=folder.id,
        name=request.name,
    )
    if existing_file:
        raise DuplicateFileNameError

    canonical_object_key = storage.get_object_key(request.blob_hash)
    blob = repository.get_blob_for_update(
        session=session,
        blob_hash=request.blob_hash,
    )
    existing_claim = repository.get_blob_claim(
        session=session,
        owner_id=owner_id,
        blob_hash=request.blob_hash,
    )
    pending_upload = None
    pending_object_key = None

    if blob:
        if blob.size_bytes != request.size_bytes:
            raise ObjectSizeMismatchError
        if not existing_claim:
            pending_upload = repository.get_latest_pending_upload(
                session=session,
                owner_id=owner_id,
                blob_hash=request.blob_hash,
            )
            if pending_upload is None:
                raise ObjectNotUploadedError
    else:
        pending_upload = repository.get_latest_pending_upload(
            session=session,
            owner_id=owner_id,
            blob_hash=request.blob_hash,
        )
        if pending_upload is None:
            raise ObjectNotUploadedError

    if pending_upload is not None:
        pending_object_key = pending_upload.object_key
        if pending_upload.size_bytes != request.size_bytes:
            raise ObjectSizeMismatchError

        if pending_upload.mime_type != request.mime_type:
            raise ObjectContentTypeMismatchError

        try:
            object_stat = storage.stat_object(
                object_key=pending_upload.object_key,
                include_checksum=True,
            )
        except storage.ObjectNotFoundError:
            raise ObjectNotUploadedError

        if object_stat.size_bytes != request.size_bytes:
            raise ObjectSizeMismatchError

        if object_stat.content_type and object_stat.content_type != request.mime_type:
            raise ObjectContentTypeMismatchError

        expected_checksum = storage.sha256_hex_to_base64(request.blob_hash)
        if object_stat.checksum_sha256 != expected_checksum:
            raise ObjectHashMismatchError

    if blob is None:
        if pending_object_key is None:
            raise ObjectNotUploadedError
        storage.copy_object(
            source_object_key=pending_object_key,
            destination_object_key=canonical_object_key,
        )
        try:
            blob = repository.create_blob(
                session=session,
                blob_hash=request.blob_hash,
                object_key=canonical_object_key,
                size_bytes=request.size_bytes,
            )
        except repository.DuplicateFileBlobRepositoryError:
            blob = repository.get_blob_for_update(
                session=session,
                blob_hash=request.blob_hash,
            )
            if blob is None:
                raise
            if blob.size_bytes != request.size_bytes:
                raise ObjectSizeMismatchError

    try:
        repository.ensure_blob_claim(
            session=session,
            owner_id=owner_id,
            blob_hash=request.blob_hash,
        )
        repository.increment_blob_ref_count(blob=blob)
        file = repository.create_file(
            session=session,
            owner_id=owner_id,
            folder_id=folder.id,
            request=request,
            commit=False,
        )
        if pending_upload is not None:
            repository.delete_pending_upload(
                session=session,
                pending_upload=pending_upload,
            )
        session.commit()
        session.refresh(file)
    except repository.DuplicateFileNameRepositoryError:
        session.rollback()
        raise DuplicateFileNameError
    if pending_object_key is not None:
        try:
            storage.delete_object(object_key=pending_object_key)
        except Exception:
            logger.exception("Failed to delete completed pending upload object")
    return StoredFilePublic.model_validate(file)


def delete_file(*, session: Session, owner_id: uuid.UUID, file_id: uuid.UUID) -> None:
    file = repository.get_file_by_id(
        session=session,
        owner_id=owner_id,
        file_id=file_id,
    )
    if not file:
        raise StoredFileNotFoundError

    blob = repository.get_blob_for_update(
        session=session,
        blob_hash=file.blob_hash,
    )
    if blob is None:
        raise BlobIntegrityError("File blob metadata is missing")

    object_key = blob.object_key
    repository.delete_file(session=session, file=file)
    repository.decrement_blob_ref_count(blob=blob)

    should_delete_object = blob.ref_count == 0
    if should_delete_object:
        session.flush()
        repository.delete_blob(session=session, blob=blob)

    session.commit()

    if should_delete_object:
        try:
            storage.delete_object(object_key=object_key)
        except Exception:
            logger.exception("Failed to delete unreferenced file blob object")


def delete_folder(
    *, session: Session, owner_id: uuid.UUID, folder_id: uuid.UUID
) -> None:
    folder = repository.get_folder_by_id(
        session=session,
        owner_id=owner_id,
        folder_id=folder_id,
    )
    if not folder or folder.path == ROOT_FOLDER_PATH:
        raise FolderNotFoundError

    subtree_folders = repository.list_folder_subtree(
        session=session,
        owner_id=owner_id,
        path=folder.path,
        for_update=True,
    )

    folder_ids = [subtree_folder.id for subtree_folder in subtree_folders]
    files = repository.list_files_in_folders(
        session=session,
        owner_id=owner_id,
        folder_ids=folder_ids,
    )
    delete_counts = Counter(file.blob_hash for file in files)
    blobs = repository.list_blobs_for_update(
        session=session,
        blob_hashes=list(delete_counts),
    )
    blobs_by_hash = {blob.blob_hash: blob for blob in blobs}
    missing_blob_hashes = set(delete_counts) - set(blobs_by_hash)
    if missing_blob_hashes:
        raise BlobIntegrityError("File blob metadata is missing")

    object_keys_to_delete: list[str] = []
    repository.delete_files(session=session, files=files)
    session.flush()

    for blob_hash, delete_count in delete_counts.items():
        blob = blobs_by_hash[blob_hash]
        blob.ref_count -= delete_count
        if blob.ref_count < 0:
            raise BlobIntegrityError("File blob ref_count would become negative")
        if blob.ref_count == 0:
            object_keys_to_delete.append(blob.object_key)
            repository.delete_blob(session=session, blob=blob)

    session.flush()
    repository.delete_folder(session=session, folder=folder)
    session.commit()

    for object_key in object_keys_to_delete:
        try:
            storage.delete_object(object_key=object_key)
        except Exception:
            logger.exception("Failed to delete unreferenced folder blob object")


def create_presigned_download(
    *, session: Session, user_id: uuid.UUID, file_id: uuid.UUID
) -> PresignDownloadResponse:
    file = repository.get_downloadable_file_by_id(
        session=session,
        user_id=user_id,
        file_id=file_id,
    )
    if not file:
        raise StoredFileNotFoundError

    object_key = storage.get_object_key(file.blob_hash)
    download_url = storage.create_presigned_download_url(
        object_key=object_key,
        filename=file.name,
    )

    return PresignDownloadResponse(
        download_url=download_url,
        expires_in=settings.S3_PRESIGNED_URL_EXPIRES_SECONDS,
    )


def share_file(
    *,
    session: Session,
    owner_id: uuid.UUID,
    file_id: uuid.UUID,
    request: FileShareCreate,
) -> FileSharePublic:
    file = repository.get_file_by_id(
        session=session,
        owner_id=owner_id,
        file_id=file_id,
    )
    if not file:
        raise StoredFileNotFoundError

    recipient = repository.get_user_by_email(
        session=session,
        email=str(request.recipient_email),
    )
    if not recipient:
        raise ShareRecipientNotFoundError
    if recipient.id == owner_id:
        raise CannotShareWithOwnerError
    if not recipient.is_active:
        raise ShareRecipientInactiveError

    try:
        share = repository.create_file_share(
            session=session,
            file_id=file.id,
            recipient_id=recipient.id,
        )
    except repository.DuplicateFileShareRepositoryError:
        raise DuplicateFileShareError

    return FileSharePublic(
        id=share.id,
        file_id=share.file_id,
        recipient_email=recipient.email,
        created_at=share.created_at,
    )


def get_files_shared_with_user(
    *, session: Session, recipient_id: uuid.UUID
) -> SharedFilesPublic:
    rows = repository.list_files_shared_with_user(
        session=session,
        recipient_id=recipient_id,
    )
    data = [
        SharedFilePublic(
            id=file.id,
            name=file.name,
            mime_type=file.mime_type,
            category=file.category,
            size_bytes=file.size_bytes,
            owner_email=owner_email,
            shared_at=shared_at,
        )
        for file, owner_email, shared_at in rows
    ]
    return SharedFilesPublic(data=data, count=len(data))


def get_file_shares(
    *, session: Session, owner_id: uuid.UUID, file_id: uuid.UUID
) -> FileSharesPublic:
    file = repository.get_file_by_id(
        session=session,
        owner_id=owner_id,
        file_id=file_id,
    )
    if not file:
        raise StoredFileNotFoundError

    data = [
        FileSharePublic(
            id=share.id,
            file_id=share.file_id,
            recipient_email=recipient_email,
            created_at=share.created_at,
        )
        for share, recipient_email in repository.list_file_shares(
            session=session,
            file_id=file.id,
        )
    ]
    return FileSharesPublic(data=data, count=len(data))


def revoke_file_share(
    *,
    session: Session,
    owner_id: uuid.UUID,
    file_id: uuid.UUID,
    share_id: uuid.UUID,
) -> None:
    file = repository.get_file_by_id(
        session=session,
        owner_id=owner_id,
        file_id=file_id,
    )
    if not file:
        raise StoredFileNotFoundError

    share = repository.get_file_share(
        session=session,
        file_id=file.id,
        share_id=share_id,
    )
    if not share:
        raise FileShareNotFoundError

    repository.delete_file_share(session=session, share=share)
