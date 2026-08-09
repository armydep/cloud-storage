import re
import uuid
from datetime import datetime
from enum import Enum

from pydantic import EmailStr, field_validator
from sqlmodel import Field, SQLModel

from app.files.models import FolderBase, StoredFileBase

SHA256_HEX_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")
LTREE_PATH_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


class FileCategory(str, Enum):
    image = "image"
    video = "video"
    audio = "audio"
    document = "document"
    spreadsheet = "spreadsheet"
    archive = "archive"
    other = "other"


class FileUploadMetadataBase(SQLModel):
    folder_path: str = Field(min_length=1, max_length=1024)
    name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=255)
    category: FileCategory
    blob_hash: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(gt=0)

    @field_validator("folder_path")
    @classmethod
    def validate_folder_path(cls, value: str) -> str:
        if not LTREE_PATH_PATTERN.fullmatch(value):
            raise ValueError("folder_path must be a valid ltree path")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if "/" in value:
            raise ValueError("name must not contain '/'")
        return value

    @field_validator("blob_hash")
    @classmethod
    def validate_blob_hash(cls, value: str) -> str:
        if not SHA256_HEX_PATTERN.fullmatch(value):
            raise ValueError("blob_hash must be a 64-character SHA-256 hex string")
        return value.lower()


class PresignUploadRequest(FileUploadMetadataBase):
    pass


class PresignUploadResponse(SQLModel):
    upload_required: bool = True
    upload_url: str | None = None
    method: str | None = "PUT"
    headers: dict[str, str]
    object_key: str
    expires_in: int


class CompleteUploadRequest(FileUploadMetadataBase):
    pass


class PresignDownloadResponse(SQLModel):
    download_url: str
    method: str = "GET"
    expires_in: int


class FolderCreate(SQLModel):
    parent_path: str = Field(min_length=1, max_length=1024)
    name: str = Field(min_length=1, max_length=255)

    @field_validator("parent_path")
    @classmethod
    def validate_parent_path(cls, value: str) -> str:
        if not LTREE_PATH_PATTERN.fullmatch(value):
            raise ValueError("parent_path must be a valid ltree path")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        if "/" in value:
            raise ValueError("name must not contain '/'")
        return value


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
    created_at: datetime | None = None
    owner_email: str | None = None


class FolderWithContentsPublic(FolderPublic):
    contents: list[FolderContentPublic]


class FileShareCreate(SQLModel):
    recipient_email: EmailStr


class FileSharePublic(SQLModel):
    id: uuid.UUID
    file_id: uuid.UUID
    recipient_email: EmailStr
    created_at: datetime


class FileSharesPublic(SQLModel):
    data: list[FileSharePublic]
    count: int


class SharedFilePublic(SQLModel):
    id: uuid.UUID
    name: str
    mime_type: str
    category: str
    size_bytes: int
    owner_email: EmailStr
    shared_at: datetime


class SharedFilesPublic(SQLModel):
    data: list[SharedFilePublic]
    count: int
