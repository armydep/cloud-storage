# Backend Scaling Configuration

The backend has two scaling-sensitive resource pools:

- PostgreSQL connections, controlled by SQLAlchemy pool settings and the number
  of backend worker processes.
- The S3-compatible object-storage client, reused per backend process.

## Database connection math

Each backend worker process owns its own SQLAlchemy pool. Worst-case connection
usage is:

```text
connections per worker = DB_POOL_SIZE + DB_MAX_OVERFLOW
connections per backend container =
  BACKEND_WORKERS * (DB_POOL_SIZE + DB_MAX_OVERFLOW)
connections for backend replicas =
  replicas * BACKEND_WORKERS * (DB_POOL_SIZE + DB_MAX_OVERFLOW)
```

The default production values are:

```env
BACKEND_WORKERS=4
DB_POOL_SIZE=3
DB_MAX_OVERFLOW=2
```

That gives a worst-case of `4 * (3 + 2) = 20` PostgreSQL connections per
backend container. Two containers can therefore consume up to 40 backend
connections before counting one-off tasks such as migrations, prestart, admin
sessions, monitoring, and reserved PostgreSQL superuser connections.

Keep the total below PostgreSQL `max_connections` with operational headroom.
For a default `max_connections=100`, avoid sizing backend replicas so their
worst-case pool usage approaches 100. If you need more containers or workers,
lower per-worker pool limits or add a connection pooler such as PgBouncer.

## Database pool settings

- `BACKEND_WORKERS`: production FastAPI worker process count.
- `DB_POOL_SIZE`: steady SQLAlchemy connections kept per worker.
- `DB_MAX_OVERFLOW`: additional burst connections allowed per worker.
- `DB_POOL_RECYCLE_SECONDS`: maximum connection age before SQLAlchemy recycles
  it.
- `DB_POOL_PRE_PING`: verifies pooled connections before checkout.

Use the metrics in [Observability](observability.md) before increasing these
values. In particular, check `db_pool_checked_out_connections`,
`db_pool_overflow_connections`, and `db_pool_checkout_wait_seconds`.

## Object-storage client settings

The backend constructs one boto3 S3 client per worker process and reuses it for
presign and object metadata operations. This avoids rebuilding botocore service
models, signers, and connection pools on every request.

The client has explicit botocore network behavior:

- `S3_CONNECT_TIMEOUT_SECONDS`
- `S3_READ_TIMEOUT_SECONDS`
- `S3_MAX_ATTEMPTS`

These settings apply when the backend makes object-storage calls such as
`head_object`, `copy_object`, and `delete_object`. Presigned URL generation is
local signing work, but it still uses the cached client configuration.
