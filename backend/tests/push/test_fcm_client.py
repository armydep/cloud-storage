import json

import httpx

from app.push.fcm_client import FcmSendResult, GoogleAuthTokenProvider, HttpV1FcmClient
from tests.utils.push import fake_service_account_info


class FakeTokenProvider:
    def __init__(self, token: str = "fake-access-token") -> None:
        self.token = token
        self.calls = 0

    def get_access_token(self) -> str:
        self.calls += 1
        return self.token


def _client(handler: httpx.MockTransport) -> HttpV1FcmClient:
    return HttpV1FcmClient(
        project_id="test-project",
        token_provider=FakeTokenProvider(),
        http_client=httpx.Client(transport=handler),
    )


def test_send_posts_to_the_v1_endpoint_with_a_bearer_token_and_data_only_message() -> (
    None
):
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"name": "projects/test-project/messages/1"})

    result = _client(httpx.MockTransport(handler)).send(
        token="device-token", data={"event_type": "file_shared", "file_id": "abc"}
    )

    assert result is FcmSendResult.SUCCESS
    request = captured["request"]
    assert (
        request.url
        == "https://fcm.googleapis.com/v1/projects/test-project/messages:send"
    )
    assert request.headers["authorization"] == "Bearer fake-access-token"
    body = json.loads(request.content)
    assert body == {
        "message": {
            "token": "device-token",
            "data": {"event_type": "file_shared", "file_id": "abc"},
        }
    }


def test_send_returns_unregistered_for_the_fcm_error_code() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "error": {
                    "code": 404,
                    "message": "Requested entity was not found.",
                    "status": "NOT_FOUND",
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError",
                            "errorCode": "UNREGISTERED",
                        }
                    ],
                }
            },
        )

    result = _client(httpx.MockTransport(handler)).send(token="dead-token", data={})

    assert result is FcmSendResult.UNREGISTERED


def test_send_returns_not_found_when_no_fcm_error_code_is_present() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "error": {
                    "code": 404,
                    "message": "Requested entity was not found.",
                    "status": "NOT_FOUND",
                }
            },
        )

    result = _client(httpx.MockTransport(handler)).send(token="dead-token", data={})

    assert result is FcmSendResult.NOT_FOUND


def test_send_returns_other_error_for_an_unrelated_failure() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500, json={"error": {"code": 500, "status": "INTERNAL", "message": "x"}}
        )

    result = _client(httpx.MockTransport(handler)).send(token="any-token", data={})

    assert result is FcmSendResult.OTHER_ERROR


def test_send_returns_other_error_when_the_body_is_not_json() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream timeout")

    result = _client(httpx.MockTransport(handler)).send(token="any-token", data={})

    assert result is FcmSendResult.OTHER_ERROR


def test_close_closes_the_underlying_http_client() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    client = _client(httpx.MockTransport(handler))

    client.close()

    assert client._http_client.is_closed


def test_google_auth_token_provider_constructs_from_a_service_account_dict() -> None:
    """Parses the private key locally -- no network call, no live credential.

    This only proves construction succeeds; `get_access_token`'s refresh
    path is not exercised here, that would require a real network call to
    Google's token endpoint.
    """
    provider = GoogleAuthTokenProvider(fake_service_account_info())

    assert provider._credentials.service_account_email == (
        "test@test-project.iam.gserviceaccount.com"
    )


def test_google_auth_token_provider_returns_the_cached_token_without_refreshing() -> (
    None
):
    provider = GoogleAuthTokenProvider(fake_service_account_info())

    class _StubCredentials:
        valid = True
        token = "cached-token"

        def refresh(self, _request: object) -> None:
            raise AssertionError("should not refresh an already-valid token")

    provider._credentials = _StubCredentials()

    assert provider.get_access_token() == "cached-token"
