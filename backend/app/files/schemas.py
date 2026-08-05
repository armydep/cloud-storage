import uuid

from sqlmodel import SQLModel

from app.files.models import FolderBase, StoredFileBase


class FolderPublic(FolderBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    parent_id: uuid.UUID | None = None


class StoredFilePublic(StoredFileBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    folder_id: uuid.UUID


class FolderContentPublic(SQLModel):
    id: uuid.UUID
    name: str
    type: str
    path: str | None = None
    mime_type: str | None = None
    category: str | None = None
    blob_hash: str | None = None
    size_bytes: int | None = None


class FolderWithContentsPublic(FolderPublic):
    contents: list[FolderContentPublic]
