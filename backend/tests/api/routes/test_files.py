from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Folder, StoredFile


def test_read_root_creates_user_root(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/files/root",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "root"
    assert content["path"] == "root"
    assert content["parent_id"] is None
    assert content["contents"] == []
    assert "id" in content
    assert "owner_id" in content

    root = db.exec(
        select(Folder).where(Folder.id == content["id"])
    ).first()
    assert root is not None
    assert str(root.owner_id) == content["owner_id"]


def test_read_root_is_idempotent_for_same_user(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    first_response = client.get(
        f"{settings.API_V1_STR}/files/root",
        headers=normal_user_token_headers,
    )
    second_response = client.get(
        f"{settings.API_V1_STR}/files/root",
        headers=normal_user_token_headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["id"] == first_response.json()["id"]


def test_read_root_returns_root_contents(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    root_response = client.get(
        f"{settings.API_V1_STR}/files/root",
        headers=normal_user_token_headers,
    )
    root = root_response.json()
    child = StoredFile(
        name="report.pdf",
        owner_id=root["owner_id"],
        folder_id=root["id"],
        mime_type="application/pdf",
        category="document",
        blob_hash="abc123",
        size_bytes=12345,
    )
    db.add(child)
    db.commit()
    db.refresh(child)

    response = client.get(
        f"{settings.API_V1_STR}/files/root",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert len(content["contents"]) == 1
    assert content["contents"][0]["id"] == str(child.id)
    assert content["contents"][0]["name"] == "report.pdf"
    assert content["contents"][0]["type"] == "file"
    assert content["contents"][0]["mime_type"] == "application/pdf"
    assert content["contents"][0]["category"] == "document"
    assert content["contents"][0]["blob_hash"] == "abc123"
    assert content["contents"][0]["size_bytes"] == 12345


def test_read_root_requires_authentication(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/files/root")

    assert response.status_code == 401


def test_read_root_is_scoped_to_authenticated_user(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    superuser_response = client.get(
        f"{settings.API_V1_STR}/files/root",
        headers=superuser_token_headers,
    )
    normal_user_response = client.get(
        f"{settings.API_V1_STR}/files/root",
        headers=normal_user_token_headers,
    )

    assert superuser_response.status_code == 200
    assert normal_user_response.status_code == 200
    assert superuser_response.json()["id"] != normal_user_response.json()["id"]
    assert (
        superuser_response.json()["owner_id"]
        != normal_user_response.json()["owner_id"]
    )
