import uuid

from sqlmodel import Session

from app.core import storage
from app.core.config import settings
from app.files import repository
from app.files.schemas import (
    CompleteUploadRequest,
    FolderContentPublic,
    FolderWithContentsPublic,
    PresignDownloadResponse,
    PresignUploadRequest,
    PresignUploadResponse,
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


def get_folder_contents(
    *, session: Session, owner_id: uuid.UUID, path: str
) -> FolderWithContentsPublic:
    folder = repository.get_folder_by_path(
        session=session,
        owner_id=owner_id,
        path=path,
    )
    if not folder and path == "root":
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

    return FolderWithContentsPublic.model_validate(folder, update={"contents": contents})


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

    file = repository.create_file(
        session=session,
        owner_id=owner_id,
        folder_id=folder.id,
        request=request,
    )
    return StoredFilePublic.model_validate(file)


def create_presigned_download(
    *, session: Session, owner_id: uuid.UUID, file_id: uuid.UUID
) -> PresignDownloadResponse:
    file = repository.get_file_by_id(
        session=session,
        owner_id=owner_id,
        file_id=file_id,
    )
    if not file:
        raise StoredFileNotFoundError

    object_key = storage.get_object_key(file.blob_hash)
    download_url = storage.create_presigned_download_url(object_key=object_key)

    return PresignDownloadResponse(
        download_url=download_url,
        expires_in=settings.S3_PRESIGNED_URL_EXPIRES_SECONDS,
    )
