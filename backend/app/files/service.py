import uuid

from sqlmodel import Session

from app.files import repository
from app.files.schemas import FolderContentPublic, FolderWithContentsPublic


class FolderNotFoundError(Exception):
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
