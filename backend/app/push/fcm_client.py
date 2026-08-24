import logging
from enum import Enum
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class FcmSendResult(str, Enum):
    SUCCESS = "success"
    # FCM reports a dead token only when a send is attempted against it --
    # there is no uninstall event (design doc decision 5). Both values are
    # treated identically by the caller: prune the token.
    UNREGISTERED = "unregistered"
    NOT_FOUND = "not_found"
    OTHER_ERROR = "other_error"


class TokenProvider(Protocol):
    """A seam over OAuth2 token acquisition.

    Kept separate from FcmClient so tests can fake the HTTP transport
    without ever touching google-auth or a live service-account credential.
    """

    def get_access_token(self) -> str: ...


class GoogleAuthTokenProvider:
    def __init__(self, service_account_info: dict[str, str]) -> None:
        # Imported lazily so importing this module never requires
        # google-auth unless a real credential is actually configured.
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        self._credentials = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
            service_account_info, scopes=[FCM_SCOPE]
        )
        self._request = Request()

    def get_access_token(self) -> str:
        if not self._credentials.valid:
            self._credentials.refresh(self._request)
        token = self._credentials.token
        assert isinstance(token, str)
        return token


class FcmClient(Protocol):
    def send(self, *, token: str, data: dict[str, str]) -> FcmSendResult: ...


class HttpV1FcmClient:
    """Sends data-only messages via FCM HTTP v1.

    The HTTP transport is injectable (defaults to a real `httpx.Client`) so
    tests can supply an `httpx.MockTransport` and assert on the request
    without a network call or a live credential.
    """

    def __init__(
        self,
        *,
        project_id: str,
        token_provider: TokenProvider,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._project_id = project_id
        self._token_provider = token_provider
        self._http_client = http_client or httpx.Client(timeout=10.0)

    def send(self, *, token: str, data: dict[str, str]) -> FcmSendResult:
        url = f"https://fcm.googleapis.com/v1/projects/{self._project_id}/messages:send"
        response = self._http_client.post(
            url,
            headers={
                "Authorization": f"Bearer {self._token_provider.get_access_token()}"
            },
            json={"message": {"token": token, "data": data}},
        )
        if response.status_code == 200:
            return FcmSendResult.SUCCESS

        try:
            body = response.json()
        except ValueError:
            body = {}
        error = body.get("error", {}) if isinstance(body, dict) else {}
        status = error.get("status")
        error_code = None
        for detail in error.get("details", []) or []:
            if isinstance(detail, dict) and detail.get("errorCode"):
                error_code = detail["errorCode"]
                break

        if error_code == "UNREGISTERED":
            return FcmSendResult.UNREGISTERED
        if status == "NOT_FOUND":
            return FcmSendResult.NOT_FOUND

        logger.warning(
            "FCM send failed: status_code=%s status=%s error_code=%s",
            response.status_code,
            status,
            error_code,
        )
        return FcmSendResult.OTHER_ERROR

    def close(self) -> None:
        self._http_client.close()
