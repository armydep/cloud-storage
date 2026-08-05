from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, SessionDep
from app.files.schemas import (
    CompleteUploadRequest,
    FolderWithContentsPublic,
    PresignUploadRequest,
    PresignUploadResponse,
    StoredFilePublic,
)
from app.files.service import (
    DuplicateFileNameError,
    FolderNotFoundError,
    ObjectContentTypeMismatchError,
    ObjectNotUploadedError,
    ObjectSizeMismatchError,
    complete_upload,
    create_presigned_upload,
    get_folder_contents,
)

router = APIRouter(prefix="/files", tags=["files"])


@router.get("", response_model=FolderWithContentsPublic)
def read_files(
    session: SessionDep,
    current_user: CurrentUser,
    path: str = Query(default="root", min_length=1, max_length=1024),
) -> Any:
    """
    Return a folder and its direct contents by ltree path.

    The root folder is created lazily when path is "root". Other missing paths
    return 404.
    """
    try:
        return get_folder_contents(
            session=session,
            owner_id=current_user.id,
            path=path,
        )
    except FolderNotFoundError:
        raise HTTPException(status_code=404, detail="Folder not found")


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
        raise HTTPException(status_code=400, detail="Uploaded object content type mismatch")
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
