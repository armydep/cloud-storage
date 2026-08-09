from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _run_migrations() -> None:
    """Build the schema the same way production does.

    Schema is Alembic-only (see CLAUDE.md), so the container is migrated rather
    than filled in via ``SQLModel.metadata.create_all``. ``app/alembic/env.py``
    reads the URL from ``settings``, which already points at the container.
    Running the real migration chain also means every test run exercises it.
    """
    config = AlembicConfig(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "app" / "alembic"))
    command.upgrade(config, "head")


def _truncate_all_tables(session: Session) -> None:
    """Empty every table except Alembic's own bookkeeping.

    Read from the catalog rather than a hand-maintained model list so a newly
    added table is cleaned without anyone remembering to update this file.
    """
    connection = session.connection()
    tables = list(
        connection.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
        ).scalars()
    )
    if not tables:
        return
    targets = ", ".join(f'"{table}"' for table in tables)
    connection.execute(text(f"TRUNCATE TABLE {targets} RESTART IDENTITY CASCADE"))
    session.commit()


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    _run_migrations()
    with Session(engine) as session:
        init_db(session)
        session.commit()
        yield session
    # No cleanup: the container is destroyed in `pytest_unconfigure`.


@pytest.fixture(scope="module", autouse=True)
def reset_database(db: Session) -> Generator[None, None, None]:
    """Give every test module a clean database.

    Truncating between modules — rather than between individual tests — matches
    the module scope of `client`, `superuser_token_headers` and
    `normal_user_token_headers`: those cache a logged-in user, so wiping
    mid-module would invalidate their tokens and fail the rest of the file.

    Autouse fixtures are set up before the others at the same scope and so are
    torn down last, which puts the truncate after the token fixtures are done.
    """
    yield
    _truncate_all_tables(db)
    init_db(db)
    db.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
