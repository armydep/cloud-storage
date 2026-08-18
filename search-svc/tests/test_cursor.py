import base64

import pytest

from app.cursor import InvalidCursorError, decode_cursor, encode_cursor


def test_encode_then_decode_round_trips() -> None:
    sort_values = [12.5, 1755388800000, "file-1"]

    cursor = encode_cursor(sort_values)

    assert decode_cursor(cursor) == sort_values


@pytest.mark.parametrize(
    "raw",
    [
        "not-base64!!!",
        base64.urlsafe_b64encode(b"not json").decode(),
        base64.urlsafe_b64encode(b'"just a string"').decode(),
        base64.urlsafe_b64encode(b"[1.0, 123]").decode(),
        base64.urlsafe_b64encode(b'[1.0, 123, "a", "extra"]').decode(),
        base64.urlsafe_b64encode(b'["not-a-score", 123, "a"]').decode(),
        base64.urlsafe_b64encode(b'[1.0, "not-an-int", "a"]').decode(),
        base64.urlsafe_b64encode(b"[1.0, 123, 42]").decode(),
        base64.urlsafe_b64encode(b'[1.0, 123, ""]').decode(),
        base64.urlsafe_b64encode(b'[true, 123, "a"]').decode(),
        base64.urlsafe_b64encode(b'[1.0, true, "a"]').decode(),
    ],
)
def test_decode_rejects_malformed_or_untrusted_cursors(raw: str) -> None:
    with pytest.raises(InvalidCursorError):
        decode_cursor(raw)


def test_decode_accepts_cursor_without_base64_padding() -> None:
    # urlsafe_b64encode output can retain '=' padding; encode_cursor strips
    # it, and decode_cursor must accept the stripped form clients receive.
    cursor = encode_cursor([1.0, 123, "a"])

    assert "=" not in cursor
    assert decode_cursor(cursor) == [1.0, 123, "a"]
