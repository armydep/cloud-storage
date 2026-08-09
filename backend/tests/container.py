"""Starts the throwaway PostgreSQL container the test suite runs against.

Two ordering constraints shape this module, and both are easy to get wrong.

``app/core/db.py`` builds its engine at import time from ``settings``, so the
``POSTGRES_*`` environment has to be correct *before* anything imports ``app``.
That first import happens in ``tests/conftest.py``.

pytest loads ``tests/conftest.py`` as an *initial* conftest during argument
pre-parsing, which is **before** any ``pytest_configure`` hook runs — so
starting the container there is too late, and a rootdir ``conftest.py`` does not
help either (pytest's ``confcutdir`` never loads it). The one hook early enough
is ``pytest_load_initial_conftests``, which fires immediately before conftest
loading. Hence a plugin rather than a conftest.

``addopts = "-p tests.container"`` in ``pyproject.toml`` wires it up, so a bare
``pytest`` gets the container with no extra flags.

Real environment variables outrank the ``.env`` file in pydantic-settings, so a
developer's ``.env`` is still read for everything else while its ``POSTGRES_*``
values are overridden — their own database is never opened.
"""

import os

import pytest
from testcontainers.community.postgres import PostgresContainer

# Matches the `db` service in compose.yml. The stock image ships the contrib
# modules, so the `ltree` and `uuid-ossp` extensions created by the migrations
# are available.
POSTGRES_IMAGE = "postgres:18"

# Set to the container's mapped port. `tests/conftest.py` refuses to migrate or
# truncate unless the engine actually points there, so a run that somehow loses
# this plugin fails loudly instead of rewriting a real database.
CONTAINER_PORT_ENV_VAR = "BACKEND_TEST_CONTAINER_PORT"


def pytest_load_initial_conftests(early_config: pytest.Config) -> None:
    container = PostgresContainer(POSTGRES_IMAGE)
    container.start()
    # Registered immediately, and before anything below can fail. pytest drains
    # these finalizers unconditionally — unlike `pytest_unconfigure`, which is
    # skipped entirely when startup fails before the config is marked
    # configured. That window is real: `tests/conftest.py` imports `app` in the
    # very next hook, and an ImportError there would otherwise orphan the
    # container.
    early_config.add_cleanup(container.stop)

    port = str(container.get_exposed_port(5432))
    os.environ["POSTGRES_SERVER"] = container.get_container_host_ip()
    os.environ["POSTGRES_PORT"] = port
    os.environ["POSTGRES_DB"] = container.dbname
    os.environ["POSTGRES_USER"] = container.username
    os.environ["POSTGRES_PASSWORD"] = container.password
    os.environ[CONTAINER_PORT_ENV_VAR] = port
