"""Starts the throwaway Postgres and RabbitMQ containers the test suite runs
against.

Two ordering constraints shape this module, and both are easy to get wrong.

``app/core/db.py`` builds its engine at import time from ``settings``, so the
``POSTGRES_*`` environment has to be correct *before* anything imports ``app``.
``RABBITMQ_USER`` and ``RABBITMQ_PASSWORD`` have no defaults either (see
``app/core/config.py``), so the same constraint applies to them even though
nothing opens a broker connection at import time: the ``Settings()`` singleton
itself is built at import of ``app.core.config`` and raises immediately if
they're missing. That first import happens in ``tests/conftest.py``.

pytest loads ``tests/conftest.py`` as an *initial* conftest during argument
pre-parsing, which is **before** any ``pytest_configure`` hook runs — so
starting the containers there is too late, and a rootdir ``conftest.py`` does
not help either (pytest's ``confcutdir`` never loads it). The one hook early
enough is ``pytest_load_initial_conftests``, which fires immediately before
conftest loading. Hence a plugin rather than a conftest.

``addopts = "-p tests.container"`` in ``pyproject.toml`` wires it up, so a bare
``pytest`` gets both containers with no extra flags.

Real environment variables outrank the ``.env`` file in pydantic-settings, so a
developer's ``.env`` is still read for everything else while its ``POSTGRES_*``
and ``RABBITMQ_*`` values are overridden — their own database and broker are
never opened.
"""

import os

import pytest
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.rabbitmq import RabbitMqContainer

# Matches the `db` service in compose.yml. The stock image ships the contrib
# modules, so the `ltree` and `uuid-ossp` extensions created by the migrations
# are available.
POSTGRES_IMAGE = "postgres:18"

# Matches the `rabbitmq` service in compose.yml.
RABBITMQ_IMAGE = "rabbitmq:4.3-management"

# Set to the container's mapped port. `tests/conftest.py` refuses to migrate or
# truncate unless the engine actually points there, so a run that somehow loses
# this plugin fails loudly instead of rewriting a real database.
CONTAINER_PORT_ENV_VAR = "BACKEND_TEST_CONTAINER_PORT"


def pytest_load_initial_conftests(early_config: pytest.Config) -> None:
    postgres = PostgresContainer(POSTGRES_IMAGE)
    postgres.start()
    # Registered immediately, and before anything below can fail. pytest drains
    # these finalizers unconditionally — unlike `pytest_unconfigure`, which is
    # skipped entirely when startup fails before the config is marked
    # configured. That window is real: `tests/conftest.py` imports `app` in the
    # very next hook, and an ImportError there would otherwise orphan the
    # container.
    early_config.add_cleanup(postgres.stop)

    port = str(postgres.get_exposed_port(5432))
    os.environ["POSTGRES_SERVER"] = postgres.get_container_host_ip()
    os.environ["POSTGRES_PORT"] = port
    os.environ["POSTGRES_DB"] = postgres.dbname
    os.environ["POSTGRES_USER"] = postgres.username
    os.environ["POSTGRES_PASSWORD"] = postgres.password
    os.environ[CONTAINER_PORT_ENV_VAR] = port

    rabbitmq = RabbitMqContainer(RABBITMQ_IMAGE)
    rabbitmq.start()
    early_config.add_cleanup(rabbitmq.stop)

    os.environ["RABBITMQ_HOST"] = rabbitmq.get_container_host_ip()
    os.environ["RABBITMQ_PORT"] = str(rabbitmq.get_exposed_port(rabbitmq.port))
    os.environ["RABBITMQ_USER"] = rabbitmq.username
    os.environ["RABBITMQ_PASSWORD"] = rabbitmq.password
