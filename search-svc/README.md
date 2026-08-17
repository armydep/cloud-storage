# Search service

`search-svc` owns the `/api/v1/search` API prefix. Slice 1 validates the shared
backend JWT and request contract, then returns empty search results; it has no
PostgreSQL, RabbitMQ, or Elasticsearch dependency.

From this directory:

```bash
uv sync
uv run pytest
uv run bash scripts/lint.sh
```

In the local compose stack, clients reach the service through Traefik at
`http://api.localhost/api/v1/search/*`. The frontend uses that Traefik origin for
all API calls, matching production routing. `backend` remains published directly
at `http://localhost:8000` for debugging only.
