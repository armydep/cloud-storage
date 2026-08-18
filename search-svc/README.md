# Search service

`search-svc` owns the `/api/v1/search` API prefix and answers queries from its
own Elasticsearch index rather than reading `backend`'s PostgreSQL database. It
never reads Postgres and is given no database credentials (decision 2 in
`docs/phases/phase-10-search-service.md`).

A separate process, the indexer (`app/indexer.py`, run as the `search-indexer`
compose service), keeps that index up to date. It consumes `file_created`,
`file_deleted` and `folder_deleted` events off the `q.search` queue -- the same
RabbitMQ exchange `backend`'s notification workers already use -- and applies
them to Elasticsearch. `search-svc` and `search-indexer` keep their own copies
of the queue/exchange names and event constants rather than importing from
`backend`; the strings are a contract, not a shared dependency (see
`app/broker.py` and `app/events.py`).

From this directory:

```bash
uv sync
uv run pytest
uv run bash scripts/lint.sh
```

`uv run pytest` includes a real Elasticsearch integration test
(`tests/test_es_index.py`) that starts a throwaway container via
`testcontainers`, so Docker must be running for the full suite; the rest of the
suite (`tests/test_api.py`, `tests/test_broker.py`, `tests/test_indexer.py`,
`tests/test_query.py`, `tests/test_cursor.py`, `tests/test_search_service.py`,
`tests/test_es_index_availability.py`) needs no external services -- query
construction and pagination are tested behind the `SearchIndex` protocol with
a fake, the same way the indexer's tests are.

In the local compose stack, clients reach the service through Traefik at
`http://api.localhost/api/v1/search/*`. The frontend uses that Traefik origin for
all API calls, matching production routing. `backend` remains published directly
at `http://localhost:8000` for debugging only.

## Elasticsearch

Single node, no clustering or replicas (decision 3) -- the index is created
with `number_of_replicas: 0`, since a lone node can never satisfy any positive
replica count; leaving the default would keep the cluster permanently yellow
and make every index-creation call block for ~30s waiting on shard allocation
before giving up.

No ingress: Elasticsearch is reachable only by `search-svc`/`search-indexer` on
the internal compose network, never through Traefik, and its port is not
published in production (decision 9). `compose.override.yml` publishes
`9200:9200` for local debugging only, the same way `db` and `rabbitmq` do.

Two things to get right locally, or the container fails silently:

- `ES_JAVA_OPTS=-Xms512m -Xmx512m` is set explicitly in `compose.yml` --
  Elasticsearch's default heap sizing assumes far more memory than a dev
  laptop typically gives Docker.
- Linux hosts need the kernel parameter `vm.max_map_count` raised, or
  Elasticsearch refuses to start with no error visible to `docker compose`:
  `sudo sysctl -w vm.max_map_count=262144` (does not persist across reboots).

The index (`files-v1`, alias `files`) is created through its alias from the
first write (decision 10), so a future mapping change can build `files-v2` and
swap the alias without downtime. The `name` field uses a custom analyzer that
splits on `_`, `-` and `.` before tokenizing, so `report_2024-final.pdf`
matches searches for `report`, `2024`, or `final` (decision 14) -- see
`app/es_index.py` for the mapping and the mapping char filter, which must use
Elasticsearch's unicode escape notation for a whitespace target rather than a
literal trailing space (Elasticsearch trims a literal one, silently turning
the replacement into a no-op removal instead).
