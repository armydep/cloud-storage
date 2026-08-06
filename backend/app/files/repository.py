import uuid
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.files.models import FileShare, Folder, StoredFile
from app.files.schemas import CompleteUploadRequest
from app.models import User

ROOT_FOLDER_PATH = "root"


class DuplicateFileNameRepositoryError(Exception):
    pass


class DuplicateFolderRepositoryError(Exception):
    pass


class DuplicateFileShareRepositoryError(Exception):
    pass


def get_folder_by_path(
    *, session: Session, owner_id: uuid.UUID, path: str
) -> Folder | None:
    statement = select(Folder).where(
        Folder.owner_id == owner_id,
        Folder.path == path,
    )
    return session.exec(statement).first()


def create_root_folder(*, session: Session, owner_id: uuid.UUID) -> Folder:
    """
    Create the owner's root folder, tolerating a lost creation race.

    Two concurrent first requests can both find no root and both try to
    insert one. uq_folders_owner_path lets the loser fail on commit and read
    the winner's row instead of raising past the caller.
    """
    folder = Folder(name=ROOT_FOLDER_PATH, path=ROOT_FOLDER_PATH, owner_id=owner_id)
    session.add(folder)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = get_folder_by_path(
            session=session, owner_id=owner_id, path=ROOT_FOLDER_PATH
        )
        if existing is None:
            raise
        return existing
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


def create_folder(
    *,
    session: Session,
    owner_id: uuid.UUID,
    parent_id: uuid.UUID,
    name: str,
    path: str,
) -> Folder:
    folder = Folder(
        owner_id=owner_id,
        parent_id=parent_id,
        name=name,
        path=path,
    )
    try:
        session.add(folder)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DuplicateFolderRepositoryError
    session.refresh(folder)
    return folder


def get_file_by_id(
    *, session: Session, owner_id: uuid.UUID, file_id: uuid.UUID
) -> StoredFile | None:
    statement = select(StoredFile).where(
        StoredFile.owner_id == owner_id,
        StoredFile.id == file_id,
    )
    return session.exec(statement).first()


def get_downloadable_file_by_id(
    *, session: Session, user_id: uuid.UUID, file_id: uuid.UUID
) -> StoredFile | None:
    statement = (
        select(StoredFile)
        .outerjoin(FileShare, col(FileShare.file_id) == col(StoredFile.id))
        .where(
            col(StoredFile.id) == file_id,
            or_(
                col(StoredFile.owner_id) == user_id,
                col(FileShare.recipient_id) == user_id,
            ),
        )
    )
    return session.exec(statement).first()


def get_user_by_email(*, session: Session, email: str) -> User | None:
    return session.exec(select(User).where(User.email == email)).first()


def create_file_share(
    *, session: Session, file_id: uuid.UUID, recipient_id: uuid.UUID
) -> FileShare:
    share = FileShare(file_id=file_id, recipient_id=recipient_id)
    try:
        session.add(share)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DuplicateFileShareRepositoryError
    session.refresh(share)
    return share


def list_files_shared_with_user(
    *, session: Session, recipient_id: uuid.UUID
) -> list[tuple[StoredFile, str, datetime]]:
    statement = (
        select(StoredFile, User.email, FileShare.created_at)
        .join(FileShare, col(FileShare.file_id) == col(StoredFile.id))
        .join(User, col(User.id) == col(StoredFile.owner_id))
        .where(col(FileShare.recipient_id) == recipient_id)
        .order_by(col(FileShare.created_at).desc(), col(FileShare.id).desc())
    )
    return list(session.exec(statement).all())


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
    try:
        session.add(file)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DuplicateFileNameRepositoryError
    session.refresh(file)
    return file
