import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, UniqueConstraint, cast
from sqlalchemy.types import UserDefinedType
from sqlmodel import Field, SQLModel


class LtreeType(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        return "LTREE"

    def bind_expression(self, bindvalue: Any) -> Any:
        # Emit `path = CAST(:param AS LTREE)` instead of relying on Postgres
        # inferring the parameter type from context, which raises a raw
        # syntax error (not a client-facing 4xx) for malformed input.
        return cast(bindvalue, self)


class FolderBase(SQLModel):
    path: str = Field(min_length=1, max_length=1024, sa_type=LtreeType)  # type: ignore
    name: str = Field(min_length=1, max_length=255)


class Folder(FolderBase, table=True):
    __tablename__ = "folders"
    # Mirrors the indexes created in migration b4c7d8e9f012 plus the two
    # composite ones added in b5e2a91c7f34, so autogenerate sees no drift.
    __table_args__ = (
        UniqueConstraint("owner_id", "path", name="uq_folders_owner_path"),
        UniqueConstraint("parent_id", "name", name="uq_folders_parent_name"),
        Index("ix_folders_owner_id", "owner_id"),
        Index("ix_folders_owner_parent", "owner_id", "parent_id"),
        Index("ix_folders_path_gist", "path", postgresql_using="gist"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    parent_id: uuid.UUID | None = Field(
        default=None, foreign_key="folders.id", nullable=True
    )


class StoredFileBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=64)
    blob_hash: str = Field(min_length=1, max_length=128)
    size_bytes: int = Field(ge=0, sa_type=BigInteger)  # type: ignore


class StoredFile(StoredFileBase, table=True):
    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("folder_id", "name", name="uq_files_folder_name"),
        Index("ix_files_owner_id", "owner_id"),
        Index("ix_files_folder_id", "folder_id"),
        Index("ix_files_blob_hash", "blob_hash"),
        Index("ix_files_owner_folder", "owner_id", "folder_id"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    folder_id: uuid.UUID = Field(
        foreign_key="folders.id", nullable=False, ondelete="CASCADE"
    )


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


class FileShare(SQLModel, table=True):
    __tablename__ = "file_shares"
    __table_args__ = (
        UniqueConstraint(
            "file_id", "recipient_id", name="uq_file_shares_file_recipient"
        ),
        Index("ix_file_shares_file_id", "file_id"),
        Index("ix_file_shares_recipient_id", "recipient_id"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    file_id: uuid.UUID = Field(
        foreign_key="files.id", nullable=False, ondelete="CASCADE"
    )
    recipient_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )
