import re
from enum import Enum

from pydantic import BaseModel, Field

LTREE_PATH_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


class FileCategory(str, Enum):
    image = "image"
    video = "video"
    audio = "audio"
    document = "document"
    spreadsheet = "spreadsheet"
    archive = "archive"
    other = "other"


class SearchResponse(BaseModel):
    results: list[dict[str, object]] = Field(default_factory=list)
    next_cursor: str | None = None


class HealthResponse(BaseModel):
    status: str
    index: str
    engine: str
