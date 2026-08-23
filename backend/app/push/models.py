import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models import get_datetime_utc


class DeviceToken(SQLModel, table=True):
    __tablename__ = "device_tokens"
    __table_args__ = (
        UniqueConstraint("token", name="uq_device_tokens_token"),
        Index("ix_device_tokens_user_id", "user_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # A device is a device, not a per-user registration -- the same
    # installation registering under a second account moves this row rather
    # than duplicating it (design doc: Token lifecycle, decision 6). That
    # reassignment is what an unregister-on-logout omission falls back on.
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    token: str = Field(sa_type=Text, nullable=False)
    # 'android' for now; iOS/APNs is out of scope but this column means
    # adding it later is a row, not a migration (design doc decision 10).
    platform: str = Field(sa_type=Text, nullable=False)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
        nullable=False,
    )
    last_seen_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
        nullable=False,
    )
