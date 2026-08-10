from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User
from app.notifications import repository
from app.notifications.events import USER_REGISTERED
from app.notifications.models import Notification


def _seed_notification(
    db: Session, *, recipient: User, created_at: datetime | None = None
) -> Notification:
    outbox = repository.enqueue_user_registered(session=db, user=recipient)
    db.commit()
    notification = repository.insert_notification(
        session=db,
        outbox_id=outbox.id,
        user_id=recipient.id,
        event_type=USER_REGISTERED,
        payload=outbox.payload,
    )
    db.commit()
    assert notification is not None
    if created_at is not None:
        notification.created_at = created_at
        db.add(notification)
        db.commit()
        db.refresh(notification)
    return notification


def test_notifications_require_authentication(client: TestClient) -> None:
    assert client.get(f"{settings.API_V1_STR}/notifications").status_code == 401
    assert (
        client.get(f"{settings.API_V1_STR}/notifications/unread-count").status_code
        == 401
    )


def test_read_notifications_returns_only_callers_notifications(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    normal_user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert normal_user is not None
    assert superuser is not None

    mine = _seed_notification(db, recipient=normal_user)
    _seed_notification(db, recipient=superuser)

    response = client.get(
        f"{settings.API_V1_STR}/notifications", headers=normal_user_token_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["data"]] == [str(mine.id)]


def test_read_notifications_paginates_with_keyset_cursor(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    normal_user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert normal_user is not None
    base = datetime.now(timezone.utc)
    first = _seed_notification(db, recipient=normal_user, created_at=base)
    second = _seed_notification(
        db, recipient=normal_user, created_at=base + timedelta(seconds=1)
    )
    third = _seed_notification(
        db, recipient=normal_user, created_at=base + timedelta(seconds=2)
    )

    first_page = client.get(
        f"{settings.API_V1_STR}/notifications",
        headers=normal_user_token_headers,
        params={"limit": 2},
    ).json()
    assert [item["id"] for item in first_page["data"]] == [
        str(third.id),
        str(second.id),
    ]
    assert first_page["next_cursor"] is not None

    second_page = client.get(
        f"{settings.API_V1_STR}/notifications",
        headers=normal_user_token_headers,
        params={"limit": 2, "cursor": first_page["next_cursor"]},
    ).json()
    assert [item["id"] for item in second_page["data"]] == [str(first.id)]
    assert second_page["next_cursor"] is None


def test_read_notifications_rejects_invalid_cursor(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/notifications",
        headers=normal_user_token_headers,
        params={"cursor": "not-a-valid-cursor!!"},
    )

    assert response.status_code == 422


def test_read_notifications_unread_only_filter(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    normal_user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert normal_user is not None
    unread = _seed_notification(db, recipient=normal_user)
    read = _seed_notification(db, recipient=normal_user)
    repository.mark_notification_read(session=db, notification=read)

    response = client.get(
        f"{settings.API_V1_STR}/notifications",
        headers=normal_user_token_headers,
        params={"unread_only": True},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == [str(unread.id)]


def test_read_unread_count(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    normal_user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert normal_user is not None
    _seed_notification(db, recipient=normal_user)
    _seed_notification(db, recipient=normal_user)

    response = client.get(
        f"{settings.API_V1_STR}/notifications/unread-count",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200
    assert response.json() == {"count": 2}


def test_mark_notification_read_marks_only_target(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    normal_user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert normal_user is not None
    target = _seed_notification(db, recipient=normal_user)
    sibling = _seed_notification(db, recipient=normal_user)

    response = client.post(
        f"{settings.API_V1_STR}/notifications/{target.id}/read",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200
    assert response.json()["read_at"] is not None

    db.refresh(sibling)
    assert sibling.read_at is None


def test_mark_notification_read_cross_user_returns_404(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    superuser = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert superuser is not None
    others_notification = _seed_notification(db, recipient=superuser)

    response = client.post(
        f"{settings.API_V1_STR}/notifications/{others_notification.id}/read",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 404


def test_mark_all_notifications_read(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    normal_user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert normal_user is not None
    first = _seed_notification(db, recipient=normal_user)
    second = _seed_notification(db, recipient=normal_user)

    response = client.post(
        f"{settings.API_V1_STR}/notifications/read-all",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 204

    db.refresh(first)
    db.refresh(second)
    assert first.read_at is not None
    assert second.read_at is not None
