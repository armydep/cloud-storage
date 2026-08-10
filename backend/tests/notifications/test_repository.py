import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app import crud
from app.models import User, UserCreate
from app.notifications import repository
from app.notifications.events import FILE_SHARED, USER_REGISTERED
from app.notifications.models import Notification
from tests.utils.utils import random_email, random_lower_string


def _create_user(db: Session) -> User:
    user = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )
    db.commit()
    return user


def test_enqueue_file_shared_writes_expected_payload(db: Session) -> None:
    recipient = _create_user(db)
    file_id = uuid.uuid4()

    notification = repository.enqueue_file_shared(
        session=db,
        file_id=file_id,
        file_name="report.pdf",
        recipient_id=recipient.id,
        recipient_email=recipient.email,
        sharer_email="alice@example.com",
    )
    db.commit()

    assert notification.event_type == FILE_SHARED
    assert notification.payload == {
        "file_id": str(file_id),
        "file_name": "report.pdf",
        "recipient_id": str(recipient.id),
        "recipient_email": recipient.email,
        "sharer_email": "alice@example.com",
    }


def test_insert_notification_is_idempotent_on_outbox_id(db: Session) -> None:
    recipient = _create_user(db)
    outbox = repository.enqueue_user_registered(session=db, user=recipient)
    db.commit()

    first = repository.insert_notification(
        session=db,
        outbox_id=outbox.id,
        user_id=recipient.id,
        event_type=USER_REGISTERED,
        payload={"a": 1},
    )
    db.commit()
    second = repository.insert_notification(
        session=db,
        outbox_id=outbox.id,
        user_id=recipient.id,
        event_type=USER_REGISTERED,
        payload={"a": 1},
    )
    db.commit()

    assert first is not None
    assert second is None
    rows = db.exec(
        select(Notification).where(Notification.outbox_id == outbox.id)
    ).all()
    assert len(rows) == 1


def test_list_notifications_orders_desc_and_paginates_by_cursor(db: Session) -> None:
    recipient = _create_user(db)
    base = datetime.now(timezone.utc)
    created = []
    for i in range(3):
        outbox = repository.enqueue_user_registered(session=db, user=recipient)
        db.commit()
        notification = Notification(
            outbox_id=outbox.id,
            user_id=recipient.id,
            event_type=USER_REGISTERED,
            payload={"i": i},
            created_at=base + timedelta(seconds=i),
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        created.append(notification)

    first_page = repository.list_notifications(
        session=db, user_id=recipient.id, limit=2
    )
    assert [n.id for n in first_page] == [created[2].id, created[1].id]

    cursor = (first_page[-1].created_at, first_page[-1].id)
    second_page = repository.list_notifications(
        session=db, user_id=recipient.id, limit=2, cursor=cursor
    )
    assert [n.id for n in second_page] == [created[0].id]


def test_list_notifications_unread_only_filter(db: Session) -> None:
    recipient = _create_user(db)
    outbox_unread = repository.enqueue_user_registered(session=db, user=recipient)
    db.commit()
    unread = repository.insert_notification(
        session=db,
        outbox_id=outbox_unread.id,
        user_id=recipient.id,
        event_type=USER_REGISTERED,
        payload={},
    )
    db.commit()
    assert unread is not None

    outbox_read = repository.enqueue_user_registered(session=db, user=recipient)
    db.commit()
    read = repository.insert_notification(
        session=db,
        outbox_id=outbox_read.id,
        user_id=recipient.id,
        event_type=USER_REGISTERED,
        payload={},
    )
    db.commit()
    assert read is not None
    repository.mark_notification_read(session=db, notification=read)

    filtered = repository.list_notifications(
        session=db, user_id=recipient.id, limit=10, unread_only=True
    )
    assert [n.id for n in filtered] == [unread.id]


def test_count_unread_only_counts_unread_for_user(db: Session) -> None:
    recipient = _create_user(db)
    other = _create_user(db)

    assert repository.count_unread(session=db, user_id=recipient.id) == 0

    outbox = repository.enqueue_user_registered(session=db, user=recipient)
    db.commit()
    repository.insert_notification(
        session=db,
        outbox_id=outbox.id,
        user_id=recipient.id,
        event_type=USER_REGISTERED,
        payload={},
    )
    db.commit()

    assert repository.count_unread(session=db, user_id=recipient.id) == 1
    assert repository.count_unread(session=db, user_id=other.id) == 0


def test_get_notification_by_id_is_scoped_to_user(db: Session) -> None:
    owner = _create_user(db)
    other = _create_user(db)
    outbox = repository.enqueue_user_registered(session=db, user=owner)
    db.commit()
    notification = repository.insert_notification(
        session=db,
        outbox_id=outbox.id,
        user_id=owner.id,
        event_type=USER_REGISTERED,
        payload={},
    )
    db.commit()
    assert notification is not None

    assert (
        repository.get_notification_by_id(
            session=db, user_id=owner.id, notification_id=notification.id
        )
        is not None
    )
    assert (
        repository.get_notification_by_id(
            session=db, user_id=other.id, notification_id=notification.id
        )
        is None
    )


def test_mark_notification_read_is_idempotent(db: Session) -> None:
    recipient = _create_user(db)
    outbox = repository.enqueue_user_registered(session=db, user=recipient)
    db.commit()
    notification = repository.insert_notification(
        session=db,
        outbox_id=outbox.id,
        user_id=recipient.id,
        event_type=USER_REGISTERED,
        payload={},
    )
    db.commit()
    assert notification is not None
    assert notification.read_at is None

    repository.mark_notification_read(session=db, notification=notification)
    first_read_at = notification.read_at
    assert first_read_at is not None

    repository.mark_notification_read(session=db, notification=notification)
    assert notification.read_at == first_read_at


def test_mark_all_read_only_affects_target_user(db: Session) -> None:
    recipient = _create_user(db)
    other = _create_user(db)

    outbox_a = repository.enqueue_user_registered(session=db, user=recipient)
    db.commit()
    notification_a = repository.insert_notification(
        session=db,
        outbox_id=outbox_a.id,
        user_id=recipient.id,
        event_type=USER_REGISTERED,
        payload={},
    )
    outbox_b = repository.enqueue_user_registered(session=db, user=other)
    db.commit()
    notification_b = repository.insert_notification(
        session=db,
        outbox_id=outbox_b.id,
        user_id=other.id,
        event_type=USER_REGISTERED,
        payload={},
    )
    db.commit()
    assert notification_a is not None
    assert notification_b is not None

    repository.mark_all_read(session=db, user_id=recipient.id)

    db.refresh(notification_a)
    db.refresh(notification_b)
    assert notification_a.read_at is not None
    assert notification_b.read_at is None
