from typing import Any

from fastapi import APIRouter
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.models import FileEntry, FileEntryPublic

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/root", response_model=FileEntryPublic)
def read_root_file_entry(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Return the authenticated user's root folder.

    The root folder is created lazily the first time the user loads the file
    browser. Later calls return the same root folder.
    """
    statement = select(FileEntry).where(
        FileEntry.owner_id == current_user.id,
        FileEntry.parent_id.is_(None),  # type: ignore[union-attr]
        FileEntry.type == "folder",
    )
    root = session.exec(statement).first()
    if root:
        return root

    root = FileEntry(name="root", type="folder", owner_id=current_user.id)
    session.add(root)
    session.commit()
    session.refresh(root)
    return root
