from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User
from app.notifications import repository
from app.notifications.events import USER_REGISTERED
from app.notifications.models import Notification
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import random_email


def _create_recipient(
    *, client: TestClient, db: Session
) -> tuple[User, dict[str, str]]:
    """A user isolated to a single test.

    `normal_user_token_headers` is module-scoped and shared across every test
    in this file, but `reset_database` only truncates between modules (see
    conftest.py), so notifications seeded against that shared user would leak
    across tests and make count/list assertions order-dependent. A fresh user
    per test sidesteps that entirely.
    """
    email = random_email()
    headers = authentication_token_from_email(client=client, email=email, db=db)
    user = crud.get_user_by_email(session=db, email=email)
    assert user is not None
    return user, headers


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
    client: TestClient, db: Session
) -> None:
    owner, owner_headers = _create_recipient(client=client, db=db)
    other, _ = _create_recipient(client=client, db=db)

    mine = _seed_notification(db, recipient=owner)
    _seed_notification(db, recipient=other)

    response = client.get(f"{settings.API_V1_STR}/notifications", headers=owner_headers)

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["data"]] == [str(mine.id)]


def test_read_notifications_paginates_with_keyset_cursor(
    client: TestClient, db: Session
) -> None:
    recipient, headers = _create_recipient(client=client, db=db)
    base = datetime.now(timezone.utc)
    first = _seed_notification(db, recipient=recipient, created_at=base)
    second = _seed_notification(
        db, recipient=recipient, created_at=base + timedelta(seconds=1)
    )
    third = _seed_notification(
        db, recipient=recipient, created_at=base + timedelta(seconds=2)
    )

    first_page = client.get(
        f"{settings.API_V1_STR}/notifications",
        headers=headers,
        params={"limit": 2},
    ).json()
    assert [item["id"] for item in first_page["data"]] == [
        str(third.id),
        str(second.id),
    ]
    assert first_page["next_cursor"] is not None

    second_page = client.get(
        f"{settings.API_V1_STR}/notifications",
        headers=headers,
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


def test_read_notifications_unread_only_filter(client: TestClient, db: Session) -> None:
    recipient, headers = _create_recipient(client=client, db=db)
    unread = _seed_notification(db, recipient=recipient)
    read = _seed_notification(db, recipient=recipient)
    repository.mark_notification_read(session=db, notification=read)

    response = client.get(
        f"{settings.API_V1_STR}/notifications",
        headers=headers,
        params={"unread_only": True},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == [str(unread.id)]


def test_read_unread_count(client: TestClient, db: Session) -> None:
    recipient, headers = _create_recipient(client=client, db=db)
    _seed_notification(db, recipient=recipient)
    _seed_notification(db, recipient=recipient)

    response = client.get(
        f"{settings.API_V1_STR}/notifications/unread-count",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {"count": 2}


def test_mark_notification_read_marks_only_target(
    client: TestClient, db: Session
) -> None:
    recipient, headers = _create_recipient(client=client, db=db)
    target = _seed_notification(db, recipient=recipient)
    sibling = _seed_notification(db, recipient=recipient)

    response = client.post(
        f"{settings.API_V1_STR}/notifications/{target.id}/read",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["read_at"] is not None

    db.refresh(sibling)
    assert sibling.read_at is None


def test_mark_notification_read_cross_user_returns_404(
    client: TestClient, db: Session
) -> None:
    owner, _ = _create_recipient(client=client, db=db)
    _, other_headers = _create_recipient(client=client, db=db)
    others_notification = _seed_notification(db, recipient=owner)

    response = client.post(
        f"{settings.API_V1_STR}/notifications/{others_notification.id}/read",
        headers=other_headers,
    )

    assert response.status_code == 404


def test_mark_all_notifications_read(client: TestClient, db: Session) -> None:
    recipient, headers = _create_recipient(client=client, db=db)
    first = _seed_notification(db, recipient=recipient)
    second = _seed_notification(db, recipient=recipient)

    response = client.post(
        f"{settings.API_V1_STR}/notifications/read-all",
        headers=headers,
    )

    assert response.status_code == 204

    db.refresh(first)
    db.refresh(second)
    assert first.read_at is not None
    assert second.read_at is not None
