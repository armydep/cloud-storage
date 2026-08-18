import base64
import json
from typing import Any

# The cursor encodes only the last hit's Elasticsearch sort values -- never
# owner_id or any other authority. owner_id always comes from the verified
# token and is applied server-side in build_search_query, so a forged or
# replayed cursor can only ever change *where in the caller's own results* a
# page starts, never *whose* results are returned (design doc constraint 5).
_SORT_VALUE_COUNT = 3  # [_score, created_at (epoch millis), _id]


class InvalidCursorError(Exception):
    pass


def encode_cursor(sort_values: list[Any]) -> str:
    payload = json.dumps(sort_values, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> list[Any]:
    padding = "=" * (-len(cursor) % 4)
    try:
        payload = base64.urlsafe_b64decode(cursor + padding)
        sort_values = json.loads(payload)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidCursorError("Cursor is not valid base64-encoded JSON") from exc

    if not isinstance(sort_values, list) or len(sort_values) != _SORT_VALUE_COUNT:
        raise InvalidCursorError("Cursor does not encode a sort-value triple")

    score, created_at_millis, doc_id = sort_values
    if not isinstance(score, int | float) or isinstance(score, bool):
        raise InvalidCursorError("Cursor score is not a number")
    if not isinstance(created_at_millis, int) or isinstance(created_at_millis, bool):
        raise InvalidCursorError("Cursor created_at is not an integer")
    if not isinstance(doc_id, str) or not doc_id:
        raise InvalidCursorError("Cursor id is not a non-empty string")

    return sort_values
