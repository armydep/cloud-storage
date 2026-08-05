import uuid

from sqlmodel import Session, select

from app.files.models import Folder, StoredFile
from app.files.schemas import CompleteUploadRequest


def get_folder_by_path(
    *, session: Session, owner_id: uuid.UUID, path: str
) -> Folder | None:
    statement = select(Folder).where(
        Folder.owner_id == owner_id,
        Folder.path == path,
    )
    return session.exec(statement).first()


def create_root_folder(*, session: Session, owner_id: uuid.UUID) -> Folder:
    folder = Folder(name="root", path="root", owner_id=owner_id)
    session.add(folder)
    session.commit()
    session.refresh(folder)
    return folder


def list_child_folders(
    *, session: Session, owner_id: uuid.UUID, parent_id: uuid.UUID
) -> list[Folder]:
    statement = (
        select(Folder)
        .where(Folder.owner_id == owner_id, Folder.parent_id == parent_id)
        .order_by(Folder.name)
    )
    return list(session.exec(statement).all())


def list_folder_files(
    *, session: Session, owner_id: uuid.UUID, folder_id: uuid.UUID
) -> list[StoredFile]:
    statement = (
        select(StoredFile)
        .where(StoredFile.owner_id == owner_id, StoredFile.folder_id == folder_id)
        .order_by(StoredFile.name)
    )
    return list(session.exec(statement).all())


def get_file_by_id(
    *, session: Session, owner_id: uuid.UUID, file_id: uuid.UUID
) -> StoredFile | None:
    statement = select(StoredFile).where(
        StoredFile.owner_id == owner_id,
        StoredFile.id == file_id,
    )
    return session.exec(statement).first()


def get_file_by_folder_and_name(
    *, session: Session, folder_id: uuid.UUID, name: str
) -> StoredFile | None:
    statement = select(StoredFile).where(
        StoredFile.folder_id == folder_id,
        StoredFile.name == name,
    )
    return session.exec(statement).first()


def create_file(
    *,
    session: Session,
    owner_id: uuid.UUID,
    folder_id: uuid.UUID,
    request: CompleteUploadRequest,
) -> StoredFile:
    file = StoredFile(
        owner_id=owner_id,
        folder_id=folder_id,
        name=request.name,
        mime_type=request.mime_type,
        category=request.category.value,
        blob_hash=request.blob_hash,
        size_bytes=request.size_bytes,
    )
    session.add(file)
    session.commit()
    session.refresh(file)
    return file
