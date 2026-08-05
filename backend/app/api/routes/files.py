from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.models import Folder, FolderContentPublic, FolderWithContentsPublic, StoredFile

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
    statement = select(Folder).where(
        Folder.owner_id == current_user.id,
        Folder.path == path,
    )
    folder = session.exec(statement).first()
    if not folder and path == "root":
        folder = Folder(name="root", path="root", owner_id=current_user.id)
        session.add(folder)
        session.commit()
        session.refresh(folder)

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    child_folders_statement = (
        select(Folder)
        .where(Folder.owner_id == current_user.id, Folder.parent_id == folder.id)
        .order_by(Folder.name)
    )
    files_statement = (
        select(StoredFile)
        .where(StoredFile.owner_id == current_user.id, StoredFile.folder_id == folder.id)
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

    return FolderWithContentsPublic.model_validate(folder, update={"contents": contents})
