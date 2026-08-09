import os
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
from tests.container import CONTAINER_PORT_ENV_VAR
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _assert_engine_targets_container() -> None:
    """Refuse to touch anything but the throwaway container.

    Everything below migrates and truncates unconditionally, so this stands in
    for the old `_is_test_database()` guard. Normally `tests/container.py` has
    already pointed the engine at the container, but `-p no:tests.container`,
    `-o addopts=` or a plugin-ordering change would silently fall back to
    `.env` — which on a normal machine is the developer's own database.
    """
    expected_port = os.environ.get(CONTAINER_PORT_ENV_VAR)
    if expected_port is None or str(engine.url.port) != expected_port:
        raise RuntimeError(
            "Refusing to run: the engine is not pointed at the test container "
            f"(engine={engine.url.render_as_string(hide_password=True)}, "
            f"{CONTAINER_PORT_ENV_VAR}={expected_port}). The tests.container "
            "plugin must load before anything imports app."
        )


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
    """Empty every table in `public` except Alembic's own bookkeeping.

    Table names are read from the catalog rather than a hand-maintained model
    list so a newly added table is cleaned without anyone remembering this
    file. Only the `public` schema is considered — nothing here creates tables
    elsewhere, and extension-owned tables must not be truncated.
    """
    connection = session.connection()
    # Without this, a leaked open transaction on another connection would make
    # TRUNCATE block until the CI job times out instead of failing usefully.
    connection.execute(text("SET LOCAL lock_timeout = '10s'"))
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
    _assert_engine_targets_container()
    _run_migrations()
    with Session(engine) as session:
        yield session
    # No cleanup: the container is destroyed when pytest exits.


@pytest.fixture(scope="module", autouse=True)
def reset_database(db: Session) -> Generator[None, None, None]:
    """Give every test module a clean database.

    Done on the way *in* rather than at teardown, so correctness does not
    depend on fixture finalization order and the first module gets a defined
    starting state too. The leading `rollback()` matters: several tests
    deliberately provoke an `IntegrityError` and rely on a later
    `db.rollback()`, so a failed assertion in between would otherwise leave the
    session needing a rollback and make `session.connection()` raise here —
    turning one real failure into a cascade across every later module.

    Per-module rather than per-test because `client`, `superuser_token_headers`
    and `normal_user_token_headers` are module-scoped and cache a logged-in
    user; wiping mid-module would invalidate their tokens. For the same reason,
    a session-scoped fixture that seeds data would have that data truncated
    here — `db` is deliberately the only session-scoped fixture.
    """
    db.rollback()
    _truncate_all_tables(db)
    # The identity map still holds objects for rows TRUNCATE just removed.
    db.expunge_all()
    init_db(db)
    db.commit()
    yield


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
