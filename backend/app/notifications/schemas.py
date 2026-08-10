import uuid
from datetime import datetime
from typing import Any

from sqlmodel import SQLModel


class NotificationPublic(SQLModel):
    id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
    read_at: datetime | None = None


class NotificationsPublic(SQLModel):
    data: list[NotificationPublic]
    next_cursor: str | None = None


class UnreadCountPublic(SQLModel):
    count: int
