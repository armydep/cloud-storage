import uuid

from sqlalchemy import BigInteger
from sqlalchemy.types import UserDefinedType
from sqlmodel import Field, SQLModel


class LtreeType(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        return "LTREE"


class FolderBase(SQLModel):
    path: str = Field(min_length=1, max_length=1024, sa_type=LtreeType)  # type: ignore
    name: str = Field(min_length=1, max_length=255)


class Folder(FolderBase, table=True):
    __tablename__ = "folders"
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
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    folder_id: uuid.UUID = Field(
        foreign_key="folders.id", nullable=False, ondelete="CASCADE"
    )
