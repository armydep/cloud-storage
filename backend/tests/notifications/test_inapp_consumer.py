import uuid

from sqlmodel import Session, select

from app import crud
from app.models import UserCreate
from app.notifications import inapp_consumer, repository
from app.notifications.events import FILE_SHARED
from app.notifications.models import Notification
from tests.utils.utils import random_email, random_lower_string


def test_handle_inserts_notification_row_via_a_fresh_session(db: Session) -> None:
    recipient = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )
    db.commit()
    outbox = repository.enqueue_file_shared(
        session=db,
        file_id=uuid.uuid4(),
        file_name="report.pdf",
        recipient_id=recipient.id,
        recipient_email=recipient.email,
        sharer_email="alice@example.com",
    )
    db.commit()

    result = inapp_consumer._handle(FILE_SHARED, outbox.payload, str(outbox.id))

    assert result is True
    notification = db.exec(
        select(Notification).where(Notification.outbox_id == outbox.id)
    ).one()
    assert notification.user_id == recipient.id
