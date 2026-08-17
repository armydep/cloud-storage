import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

os.environ["SECRET_KEY"] = "search-service-test-secret-at-least-32-bytes"
os.environ["RABBITMQ_USER"] = "search-service-test-user"
os.environ["RABBITMQ_PASSWORD"] = "search-service-test-password"

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
