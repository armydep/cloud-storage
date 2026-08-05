from typing import Any

from fastapi import APIRouter
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.models import Folder, FolderContentPublic, FolderWithContentsPublic, StoredFile

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/root", response_model=FolderWithContentsPublic)
def read_root_file_entry(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Return the authenticated user's root folder and its contents.

    The root folder is created lazily the first time the user loads the file
    browser. Later calls return the same root folder.
    """
    statement = select(Folder).where(
        Folder.owner_id == current_user.id,
        Folder.parent_id.is_(None),  # type: ignore[union-attr]
    )
    root = session.exec(statement).first()
    if not root:
        root = Folder(name="root", path="root", owner_id=current_user.id)
        session.add(root)
        session.commit()
        session.refresh(root)

    child_folders_statement = (
        select(Folder)
        .where(Folder.owner_id == current_user.id, Folder.parent_id == root.id)
        .order_by(Folder.name)
    )
    files_statement = (
        select(StoredFile)
        .where(StoredFile.owner_id == current_user.id, StoredFile.folder_id == root.id)
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

    return FolderWithContentsPublic.model_validate(root, update={"contents": contents})
