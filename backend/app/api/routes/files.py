import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, SessionDep
from app.files.repository import ROOT_FOLDER_PATH
from app.files.schemas import (
    LTREE_PATH_PATTERN,
    CompleteUploadRequest,
    FileShareCreate,
    FileSharePublic,
    FileSharesPublic,
    FolderCreate,
    FolderPublic,
    FolderWithContentsPublic,
    PresignDownloadResponse,
    PresignUploadRequest,
    PresignUploadResponse,
    SharedFilesPublic,
    StoredFilePublic,
)
from app.files.service import (
    CannotShareWithOwnerError,
    DuplicateFileNameError,
    DuplicateFileShareError,
    DuplicateFolderNameError,
    FileShareNotFoundError,
    FolderNotFoundError,
    InvalidFolderNameError,
    ObjectContentTypeMismatchError,
    ObjectHashMismatchError,
    ObjectNotUploadedError,
    ObjectSizeMismatchError,
    ShareRecipientInactiveError,
    ShareRecipientNotFoundError,
    StoredFileNotFoundError,
    complete_upload,
    create_folder,
    create_presigned_download,
    create_presigned_upload,
    delete_file,
    get_file_shares,
    get_files_shared_with_user,
    get_folder_contents,
    revoke_file_share,
    share_file,
)

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/shared-with-me", response_model=SharedFilesPublic)
def read_files_shared_with_me(
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    return get_files_shared_with_user(
        session=session,
        recipient_id=current_user.id,
    )


@router.post("/folders", response_model=FolderPublic, status_code=201)
def create_child_folder(
    session: SessionDep,
    current_user: CurrentUser,
    request: FolderCreate,
) -> Any:
    try:
        return create_folder(
            session=session,
            owner_id=current_user.id,
            request=request,
        )
    except FolderNotFoundError:
        raise HTTPException(status_code=404, detail="Parent folder not found")
    except DuplicateFolderNameError:
        raise HTTPException(status_code=409, detail="Folder name already exists")
    except InvalidFolderNameError:
        raise HTTPException(status_code=422, detail="Folder name is invalid")


@router.get("", response_model=FolderWithContentsPublic)
def read_files(
    session: SessionDep,
    current_user: CurrentUser,
    path: str = Query(
        default=ROOT_FOLDER_PATH,
        min_length=1,
        max_length=1024,
        pattern=LTREE_PATH_PATTERN.pattern,
    ),
) -> Any:
    """
    Return a folder and its direct contents by ltree path.

    The root folder is created lazily when path is "root". Other missing paths
    return 404, and a path that is not a valid ltree returns 422.
    """
    if path.split(".", 1)[0] != ROOT_FOLDER_PATH:
        # Every folder of every user hangs off "root", so this can never match.
        raise HTTPException(status_code=404, detail="Folder not found")

    try:
        return get_folder_contents(
            session=session,
            owner_id=current_user.id,
            path=path,
        )
    except FolderNotFoundError:
        raise HTTPException(status_code=404, detail="Folder not found")


@router.post("/{file_id}/presign-download", response_model=PresignDownloadResponse)
def presign_download(
    session: SessionDep,
    current_user: CurrentUser,
    file_id: uuid.UUID,
) -> Any:
    try:
        return create_presigned_download(
            session=session,
            user_id=current_user.id,
            file_id=file_id,
        )
    except StoredFileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")


@router.delete("/{file_id}", status_code=204)
def delete_owned_file(
    session: SessionDep,
    current_user: CurrentUser,
    file_id: uuid.UUID,
) -> None:
    try:
        delete_file(
            session=session,
            owner_id=current_user.id,
            file_id=file_id,
        )
    except StoredFileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")


@router.post("/{file_id}/shares", response_model=FileSharePublic, status_code=201)
def create_file_share(
    session: SessionDep,
    current_user: CurrentUser,
    file_id: uuid.UUID,
    request: FileShareCreate,
) -> Any:
    try:
        return share_file(
            session=session,
            owner_id=current_user.id,
            file_id=file_id,
            request=request,
        )
    except StoredFileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except ShareRecipientNotFoundError:
        raise HTTPException(status_code=404, detail="Recipient not found")
    except ShareRecipientInactiveError:
        raise HTTPException(status_code=422, detail="Recipient is inactive")
    except CannotShareWithOwnerError:
        raise HTTPException(
            status_code=422,
            detail="A file cannot be shared with its owner",
        )
    except DuplicateFileShareError:
        raise HTTPException(
            status_code=409,
            detail="File is already shared with this recipient",
        )


@router.get("/{file_id}/shares", response_model=FileSharesPublic)
def read_file_shares(
    session: SessionDep,
    current_user: CurrentUser,
    file_id: uuid.UUID,
) -> Any:
    try:
        return get_file_shares(
            session=session,
            owner_id=current_user.id,
            file_id=file_id,
        )
    except StoredFileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")


@router.delete("/{file_id}/shares/{share_id}", status_code=204)
def delete_file_share(
    session: SessionDep,
    current_user: CurrentUser,
    file_id: uuid.UUID,
    share_id: uuid.UUID,
) -> None:
    try:
        revoke_file_share(
            session=session,
            owner_id=current_user.id,
            file_id=file_id,
            share_id=share_id,
        )
    except StoredFileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except FileShareNotFoundError:
        raise HTTPException(status_code=404, detail="File share not found")


@router.post("/complete-upload", response_model=StoredFilePublic)
def complete_file_upload(
    session: SessionDep,
    current_user: CurrentUser,
    request: CompleteUploadRequest,
) -> Any:
    try:
        return complete_upload(
            session=session,
            owner_id=current_user.id,
            request=request,
        )
    except FolderNotFoundError:
        raise HTTPException(status_code=404, detail="Folder not found")
    except ObjectNotUploadedError:
        raise HTTPException(status_code=400, detail="Uploaded object not found")
    except ObjectSizeMismatchError:
        raise HTTPException(status_code=400, detail="Uploaded object size mismatch")
    except ObjectContentTypeMismatchError:
        raise HTTPException(
            status_code=400, detail="Uploaded object content type mismatch"
        )
    except ObjectHashMismatchError:
        raise HTTPException(status_code=400, detail="Uploaded object hash mismatch")
    except DuplicateFileNameError:
        raise HTTPException(status_code=409, detail="File name already exists")


@router.post("/presign-upload", response_model=PresignUploadResponse)
def presign_upload(
    session: SessionDep,
    current_user: CurrentUser,
    request: PresignUploadRequest,
) -> Any:
    try:
        return create_presigned_upload(
            session=session,
            owner_id=current_user.id,
            request=request,
        )
    except FolderNotFoundError:
        raise HTTPException(status_code=404, detail="Folder not found")
