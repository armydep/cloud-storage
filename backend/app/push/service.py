import logging
import uuid
from typing import Any

from sqlmodel import Session

from app.models import User
from app.notifications.events import FILE_SHARED
from app.push import repository
from app.push.fcm_client import FcmClient, FcmSendResult
from app.push.schemas import DeviceTokenPublic

logger = logging.getLogger(__name__)

# Which events push -- a per-event decision recorded here, not a property of
# the channel (design doc decision 11). Only file_shared exists today.
PUSH_EVENT_TYPES = {FILE_SHARED}

# Decision 12: a generic, non-identifying title. The event type and file id
# are identifiers the app resolves details for; no file name ever leaves
# our servers via FCM.
GENERIC_TITLE = "You have a new notification"


def register_device_token(
    *, session: Session, user: User, token: str, platform: str
) -> DeviceTokenPublic:
    device_token = repository.register_device_token(
        session=session, user_id=user.id, token=token, platform=platform
    )
    return DeviceTokenPublic(
        id=device_token.id,
        token=device_token.token,
        platform=device_token.platform,
        created_at=device_token.created_at,
        last_seen_at=device_token.last_seen_at,
    )


def unregister_device_token(*, session: Session, user: User, token: str) -> None:
    repository.delete_device_token(session=session, user_id=user.id, token=token)


def handle_event(
    *,
    session: Session,
    fcm_client: FcmClient,
    event_type: str,
    payload: dict[str, Any],
    message_id: str,
) -> bool:
    """Push delivery for one notification-outbox event.

    Returns True when the message should be acked, False when it should be
    retried. A dead token that gets pruned is not a failure of this
    delivery; an FCM error other than a dead-token response is, and causes a
    retry of the whole message -- which is safe because the mobile client
    de-duplicates on `notification_id` (this same `message_id`), per
    decision 7 in the design doc: delivery is at-least-once and one dead
    token must never abort the others.
    """
    if event_type not in PUSH_EVENT_TYPES:
        logger.info("Ignoring unsupported push event: %s", event_type)
        return True

    recipient_id_raw = payload.get("recipient_id")
    file_id_raw = payload.get("file_id")
    if not isinstance(recipient_id_raw, str) or not isinstance(file_id_raw, str):
        logger.error("Push event missing recipient_id or file_id: %r", payload)
        return False
    try:
        recipient_id = uuid.UUID(recipient_id_raw)
    except ValueError:
        return False

    user = session.get(User, recipient_id)
    if user is None or not user.push_enabled:
        # Opted out (or gone): the feed and email channels are unaffected --
        # push_enabled is a push-channel preference only (decision 16).
        return True

    tokens = repository.list_tokens_for_user(session=session, user_id=user.id)
    if not tokens:
        return True

    data = {
        "event_type": event_type,
        "file_id": file_id_raw,
        "notification_id": message_id,
        "title": GENERIC_TITLE,
    }

    any_transient_failure = False
    for device_token in tokens:
        try:
            result = fcm_client.send(token=device_token.token, data=data)
        except Exception:
            logger.exception("FCM send raised for a token; continuing to the rest")
            any_transient_failure = True
            continue

        if result in (FcmSendResult.UNREGISTERED, FcmSendResult.NOT_FOUND):
            repository.delete_device_token(
                session=session, user_id=user.id, token=device_token.token
            )
        elif result is FcmSendResult.OTHER_ERROR:
            any_transient_failure = True

    return not any_transient_failure
