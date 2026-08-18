import uuid
from datetime import datetime, timezone

from sqlalchemy import delete as sql_delete
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.files.models import (
    FileBlob,
    FileBlobClaim,
    FileShare,
    Folder,
    PendingUpload,
    StoredFile,
)
from app.files.schemas import CompleteUploadRequest
from app.models import User

ROOT_FOLDER_PATH = "root"


class DuplicateFileNameRepositoryError(Exception):
    pass


class DuplicateFolderRepositoryError(Exception):
    pass


class DuplicateFileShareRepositoryError(Exception):
    pass


class DuplicateFileBlobRepositoryError(Exception):
    pass


class DuplicateFileBlobClaimRepositoryError(Exception):
    pass


class DuplicatePendingUploadRepositoryError(Exception):
    pass


def get_folder_by_path(
    *, session: Session, owner_id: uuid.UUID, path: str
) -> Folder | None:
    statement = select(Folder).where(
        Folder.owner_id == owner_id,
        Folder.path == path,
    )
    return session.exec(statement).first()


def get_folder_by_id(
    *, session: Session, owner_id: uuid.UUID, folder_id: uuid.UUID
) -> Folder | None:
    statement = select(Folder).where(
        Folder.owner_id == owner_id,
        Folder.id == folder_id,
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


def list_folder_subtree(
    *, session: Session, owner_id: uuid.UUID, path: str, for_update: bool = False
) -> list[Folder]:
    statement = select(Folder).where(
        Folder.owner_id == owner_id,
        col(Folder.path).op("<@")(path),
    )
    if for_update:
        statement = statement.with_for_update()
    folders = list(session.exec(statement).all())
    return sorted(
        folders,
        key=lambda folder: len(str(folder.path).split(".")),
        reverse=True,
    )


def list_folder_files(
    *, session: Session, owner_id: uuid.UUID, folder_id: uuid.UUID
) -> list[StoredFile]:
    statement = (
        select(StoredFile)
        .where(StoredFile.owner_id == owner_id, StoredFile.folder_id == folder_id)
        .order_by(StoredFile.name)
    )
    return list(session.exec(statement).all())


def list_files_in_folders(
    *, session: Session, owner_id: uuid.UUID, folder_ids: list[uuid.UUID]
) -> list[StoredFile]:
    if not folder_ids:
        return []
    statement = (
        select(StoredFile)
        .where(
            StoredFile.owner_id == owner_id,
            col(StoredFile.folder_id).in_(folder_ids),
        )
        .order_by(StoredFile.name)
    )
    return list(session.exec(statement).all())


def list_folder_files_with_owner(
    *, session: Session, owner_id: uuid.UUID, folder_id: uuid.UUID
) -> list[tuple[StoredFile, str]]:
    statement = (
        select(StoredFile, User.email)
        .join(User, col(User.id) == col(StoredFile.owner_id))
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
    *,
    session: Session,
    file_id: uuid.UUID,
    recipient_id: uuid.UUID,
    commit: bool = True,
) -> FileShare:
    share = FileShare(file_id=file_id, recipient_id=recipient_id)
    try:
        session.add(share)
        if commit:
            session.commit()
        else:
            session.flush()
    except IntegrityError:
        session.rollback()
        raise DuplicateFileShareRepositoryError
    if commit:
        session.refresh(share)
    return share


def list_file_shares(
    *, session: Session, file_id: uuid.UUID
) -> list[tuple[FileShare, str]]:
    statement = (
        select(FileShare, User.email)
        .join(User, col(User.id) == col(FileShare.recipient_id))
        .where(col(FileShare.file_id) == file_id)
        .order_by(col(FileShare.created_at).desc(), col(FileShare.id).desc())
    )
    return list(session.exec(statement).all())


def get_file_share(
    *, session: Session, file_id: uuid.UUID, share_id: uuid.UUID
) -> FileShare | None:
    statement = select(FileShare).where(
        FileShare.file_id == file_id,
        FileShare.id == share_id,
    )
    return session.exec(statement).first()


def delete_file_share(*, session: Session, share: FileShare) -> None:
    session.delete(share)
    session.commit()


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


def get_blob_by_hash(*, session: Session, blob_hash: str) -> FileBlob | None:
    return session.get(FileBlob, blob_hash)


def get_blob_for_update(*, session: Session, blob_hash: str) -> FileBlob | None:
    statement = (
        select(FileBlob).where(FileBlob.blob_hash == blob_hash).with_for_update()
    ).execution_options(populate_existing=True)
    return session.exec(statement).first()


def list_blobs_for_update(
    *, session: Session, blob_hashes: list[str]
) -> list[FileBlob]:
    if not blob_hashes:
        return []
    statement = (
        select(FileBlob)
        .where(col(FileBlob.blob_hash).in_(blob_hashes))
        .with_for_update()
    )
    return list(session.exec(statement).all())


def get_blob_claim(
    *, session: Session, owner_id: uuid.UUID, blob_hash: str
) -> FileBlobClaim | None:
    statement = select(FileBlobClaim).where(
        FileBlobClaim.owner_id == owner_id,
        FileBlobClaim.blob_hash == blob_hash,
    )
    return session.exec(statement).first()


def create_blob_claim(
    *, session: Session, owner_id: uuid.UUID, blob_hash: str
) -> FileBlobClaim:
    claim = FileBlobClaim(owner_id=owner_id, blob_hash=blob_hash)
    try:
        session.add(claim)
        session.flush()
    except IntegrityError:
        session.rollback()
        raise DuplicateFileBlobClaimRepositoryError
    return claim


def ensure_blob_claim(
    *, session: Session, owner_id: uuid.UUID, blob_hash: str
) -> FileBlobClaim:
    existing_claim = get_blob_claim(
        session=session,
        owner_id=owner_id,
        blob_hash=blob_hash,
    )
    if existing_claim:
        return existing_claim

    try:
        return create_blob_claim(
            session=session,
            owner_id=owner_id,
            blob_hash=blob_hash,
        )
    except DuplicateFileBlobClaimRepositoryError:
        existing_claim = get_blob_claim(
            session=session,
            owner_id=owner_id,
            blob_hash=blob_hash,
        )
        if existing_claim is None:
            raise
        return existing_claim


def create_pending_upload(
    *,
    session: Session,
    upload_id: uuid.UUID,
    owner_id: uuid.UUID,
    blob_hash: str,
    object_key: str,
    size_bytes: int,
    mime_type: str,
    expires_at: datetime,
) -> PendingUpload:
    pending_upload = PendingUpload(
        id=upload_id,
        owner_id=owner_id,
        blob_hash=blob_hash,
        object_key=object_key,
        size_bytes=size_bytes,
        mime_type=mime_type,
        expires_at=expires_at,
    )
    try:
        session.add(pending_upload)
        session.flush()
    except IntegrityError:
        session.rollback()
        raise DuplicatePendingUploadRepositoryError
    return pending_upload


def get_latest_pending_upload(
    *, session: Session, owner_id: uuid.UUID, blob_hash: str
) -> PendingUpload | None:
    statement = (
        select(PendingUpload)
        .where(
            PendingUpload.owner_id == owner_id,
            PendingUpload.blob_hash == blob_hash,
            PendingUpload.expires_at > datetime.now(timezone.utc),
        )
        .order_by(col(PendingUpload.created_at).desc())
    )
    return session.exec(statement).first()


def delete_pending_upload(*, session: Session, pending_upload: PendingUpload) -> None:
    session.delete(pending_upload)


def create_blob(
    *,
    session: Session,
    blob_hash: str,
    object_key: str,
    size_bytes: int,
    ref_count: int = 0,
) -> FileBlob:
    blob = FileBlob(
        blob_hash=blob_hash,
        object_key=object_key,
        size_bytes=size_bytes,
        ref_count=ref_count,
    )
    session.add(blob)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise DuplicateFileBlobRepositoryError
    return blob


def increment_blob_ref_count(*, blob: FileBlob) -> None:
    blob.ref_count += 1


def decrement_blob_ref_count(*, blob: FileBlob) -> None:
    blob.ref_count -= 1


def delete_blob(*, session: Session, blob: FileBlob) -> None:
    session.delete(blob)


def list_files_for_search_backfill(
    *, session: Session, batch_size: int, after_id: uuid.UUID | None
) -> list[tuple[StoredFile, str]]:
    """Keyset-paginated over StoredFile.id, joined to Folder for folder_path.

    Files carry no folder_path of their own -- it lives on the folder the
    file belongs to (search_backfill.py needs it for the same reason
    enqueue_file_created does at upload time). Keyset rather than offset
    pagination so a large table is never loaded into memory at once and
    scanning doesn't degrade as the backfill proceeds deeper into it.
    """
    statement = (
        select(StoredFile, Folder.path)
        .join(Folder, col(Folder.id) == col(StoredFile.folder_id))
        .order_by(col(StoredFile.id))
        .limit(batch_size)
    )
    if after_id is not None:
        statement = statement.where(col(StoredFile.id) > after_id)
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
    commit: bool = True,
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
        if commit:
            session.commit()
        else:
            session.flush()
    except IntegrityError:
        session.rollback()
        raise DuplicateFileNameRepositoryError
    if commit:
        session.refresh(file)
    return file


def delete_file(*, session: Session, file: StoredFile) -> None:
    session.execute(sql_delete(StoredFile).where(col(StoredFile.id) == file.id))
    if file in session:
        session.expunge(file)


def delete_files(*, session: Session, files: list[StoredFile]) -> None:
    for file in files:
        delete_file(session=session, file=file)


def delete_folder(*, session: Session, folder: Folder) -> None:
    session.delete(folder)


def delete_folders(*, session: Session, folders: list[Folder]) -> None:
    for folder in folders:
        delete_folder(session=session, folder=folder)
