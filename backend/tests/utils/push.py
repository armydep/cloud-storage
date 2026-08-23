from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlmodel import Session

from app.models import User
from app.push.fcm_client import FcmSendResult


def fake_service_account_info() -> dict[str, str]:
    """A structurally valid, throwaway service-account credential.

    `google.oauth2.service_account.Credentials.from_service_account_info`
    parses the private key locally (no network call), so a real RSA keypair
    generated here -- with no association to any real Google project -- is
    enough to exercise that construction path without a live credential.
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "test-key-id",
        "private_key": pem,
        "client_email": "test@test-project.iam.gserviceaccount.com",
        "client_id": "000000000000000000000",
        "token_uri": "https://oauth2.googleapis.com/token",
    }


class FakeFcmClient:
    """A test double behind the FcmClient seam -- no live credential, no

    network. Results are queued per call so a test can script a mix of
    successes, dead tokens, and transient failures across a fan-out.
    """

    def __init__(self, results: list[FcmSendResult] | None = None) -> None:
        self._results = list(results or [])
        self.calls: list[tuple[str, dict[str, str]]] = []

    def send(self, *, token: str, data: dict[str, str]) -> FcmSendResult:
        self.calls.append((token, data))
        if self._results:
            return self._results.pop(0)
        return FcmSendResult.SUCCESS


def enable_push(db: Session, user: User) -> None:
    user.push_enabled = True
    db.add(user)
    db.commit()
    db.refresh(user)
