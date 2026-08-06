import re
import uuid

from sqlmodel import Session

from app.core import storage
from app.core.config import settings
from app.files import repository
from app.files.repository import ROOT_FOLDER_PATH
from app.files.schemas import (
    CompleteUploadRequest,
    FileShareCreate,
    FileSharePublic,
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
    files = repository.list_folder_files(
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
        )
        for file in files
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

    object_key = storage.get_object_key(request.blob_hash)
    upload_url = storage.create_presigned_upload_url(
        object_key=object_key,
        mime_type=request.mime_type,
    )

    return PresignUploadResponse(
        upload_url=upload_url,
        headers={"Content-Type": request.mime_type},
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

    object_key = storage.get_object_key(request.blob_hash)
    try:
        object_stat = storage.stat_object(object_key=object_key)
    except storage.ObjectNotFoundError:
        raise ObjectNotUploadedError

    if object_stat.size_bytes != request.size_bytes:
        raise ObjectSizeMismatchError

    if object_stat.content_type and object_stat.content_type != request.mime_type:
        raise ObjectContentTypeMismatchError

    try:
        file = repository.create_file(
            session=session,
            owner_id=owner_id,
            folder_id=folder.id,
            request=request,
        )
    except repository.DuplicateFileNameRepositoryError:
        raise DuplicateFileNameError
    return StoredFilePublic.model_validate(file)


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
