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

_CONTAINER_KEY: pytest.StashKey[PostgresContainer] = pytest.StashKey()


def pytest_load_initial_conftests(early_config: pytest.Config) -> None:
    container = PostgresContainer(POSTGRES_IMAGE)
    container.start()
    early_config.stash[_CONTAINER_KEY] = container

    os.environ["POSTGRES_SERVER"] = container.get_container_host_ip()
    os.environ["POSTGRES_PORT"] = str(container.get_exposed_port(5432))
    os.environ["POSTGRES_DB"] = container.dbname
    os.environ["POSTGRES_USER"] = container.username
    os.environ["POSTGRES_PASSWORD"] = container.password


def pytest_unconfigure(config: pytest.Config) -> None:
    container = config.stash.get(_CONTAINER_KEY, None)
    if container is not None:
        container.stop()
        del config.stash[_CONTAINER_KEY]
