from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.crud import ROOT_FOLDER_PATH
from app.models import (
    LTREE_PATH_MAX_LENGTH,
    LTREE_PATH_PATTERN,
    Folder,
    FolderContentPublic,
    FolderWithContentsPublic,
    StoredFile,
)

router = APIRouter(prefix="/files", tags=["files"])


@router.get("", response_model=FolderWithContentsPublic)
def read_files(
    session: SessionDep,
    current_user: CurrentUser,
    path: str = Query(
        default=ROOT_FOLDER_PATH,
        min_length=1,
        max_length=LTREE_PATH_MAX_LENGTH,
        pattern=LTREE_PATH_PATTERN,
    ),
) -> Any:
    """
    Return a folder and its direct contents by ltree path.

    The root folder is created lazily when path is "root". Other missing paths
    return 404, and a path that is not a valid ltree returns 422.
    """
    if path.split(".")[0] != ROOT_FOLDER_PATH:
        # Every folder of every user hangs off "root", so this can never match.
        raise HTTPException(status_code=404, detail="Folder not found")

    folder: Folder | None
    if path == ROOT_FOLDER_PATH:
        folder = crud.get_or_create_root_folder(
            session=session, owner_id=current_user.id
        )
    else:
        folder = crud.get_folder_by_path(
            session=session, owner_id=current_user.id, path=path
        )

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    child_folders_statement = (
        select(Folder)
        .where(Folder.owner_id == current_user.id, Folder.parent_id == folder.id)
        .order_by(Folder.name)
    )
    files_statement = (
        select(StoredFile)
        .where(
            StoredFile.owner_id == current_user.id, StoredFile.folder_id == folder.id
        )
        .order_by(StoredFile.name)
    )
    child_folders = session.exec(child_folders_statement).all()
    files = session.exec(files_statement).all()
    contents = [
        FolderContentPublic(
            id=folder.id,
            name=folder.name,
            type="folder",
            path=folder.path,
        )
        for folder in child_folders
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
