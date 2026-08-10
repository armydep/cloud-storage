import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, SessionDep
from app.notifications.feed_service import (
    InvalidCursorError,
    NotificationNotFoundError,
    list_notifications,
    mark_all_read,
    mark_read,
    unread_count,
)
from app.notifications.schemas import (
    NotificationPublic,
    NotificationsPublic,
    UnreadCountPublic,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationsPublic)
def read_notifications(
    session: SessionDep,
    current_user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    unread_only: bool = Query(default=False),
) -> Any:
    try:
        return list_notifications(
            session=session,
            user_id=current_user.id,
            limit=limit,
            cursor=cursor,
            unread_only=unread_only,
        )
    except InvalidCursorError:
        raise HTTPException(status_code=422, detail="Invalid cursor")


@router.get("/unread-count", response_model=UnreadCountPublic)
def read_unread_count(session: SessionDep, current_user: CurrentUser) -> Any:
    return unread_count(session=session, user_id=current_user.id)


@router.post("/{notification_id}/read", response_model=NotificationPublic)
def read_notification(
    session: SessionDep,
    current_user: CurrentUser,
    notification_id: uuid.UUID,
) -> Any:
    try:
        return mark_read(
            session=session,
            user_id=current_user.id,
            notification_id=notification_id,
        )
    except NotificationNotFoundError:
        raise HTTPException(status_code=404, detail="Notification not found")


@router.post("/read-all", status_code=204)
def read_all_notifications(session: SessionDep, current_user: CurrentUser) -> None:
    mark_all_read(session=session, user_id=current_user.id)
