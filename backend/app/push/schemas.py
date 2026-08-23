import uuid
from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class DevicePlatform(str, Enum):
    android = "android"


class DeviceTokenRegister(SQLModel):
    token: str = Field(min_length=1, max_length=4096)
    platform: DevicePlatform


class DeviceTokenPublic(SQLModel):
    id: uuid.UUID
    token: str
    platform: str
    created_at: datetime
    last_seen_at: datetime
