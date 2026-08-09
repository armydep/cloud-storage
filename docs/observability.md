# Observability

The backend exposes Prometheus metrics at:

```text
GET /metrics
Authorization: Bearer <METRICS_BEARER_TOKEN>
```

The endpoint is mounted at the backend app root, outside `/api/v1`, and is
disabled unless `METRICS_BEARER_TOKEN` is configured. Do not reuse an end-user
JWT as this token; use a dedicated scrape secret.

## Local scrape example

Set a token in `.env`:

```env
METRICS_BEARER_TOKEN=replace-with-a-long-random-token
```

Then scrape the backend from another Compose service, for example Prometheus:

```yaml
scrape_configs:
  - job_name: cloud-file-storage-backend
    metrics_path: /metrics
    scheme: http
    bearer_token: replace-with-a-long-random-token
    static_configs:
      - targets:
          - backend:8000
```

For a direct local check:

```bash
curl -H "Authorization: Bearer ${METRICS_BEARER_TOKEN}" \
  http://localhost:8000/metrics
```

## Signals exposed

HTTP request metrics:

- `http_requests_total{method,endpoint,status_code}`
- `http_request_duration_seconds{method,endpoint}`

Endpoint labels use FastAPI route templates rather than raw paths, which avoids
high-cardinality labels from IDs, hashes, or folder paths.

Database pool metrics:

- `db_pool_checked_out_connections`
- `db_pool_checked_in_connections`
- `db_pool_size_connections`
- `db_pool_overflow_connections`
- `db_pool_checkout_wait_seconds`
- `db_pool_events_total{event}`

Object-storage metrics:

- `object_storage_operations_total{operation,result}`
- `object_storage_operation_duration_seconds{operation,result}`

Object-storage labels use bounded operation names such as `stat_object`,
`copy_object`, and `create_presigned_upload_url`; object keys and hashes are not
exported as labels.

## What to check before changing database pool limits

Before acting on the SCALE 2.1 / 2.2 connection-limit findings, check:

1. `db_pool_checked_out_connections` versus `db_pool_size_connections`
2. `db_pool_overflow_connections`
3. `db_pool_checkout_wait_seconds`
4. `http_request_duration_seconds` for endpoints that perform database work

If checkout wait is flat and checked-out connections are below pool capacity,
raising pool sizes or splitting services is unlikely to address the real
bottleneck. If checkout wait rises while checked-out and overflow connections
are saturated, pool sizing, worker count, and PostgreSQL `max_connections`
should be evaluated together.

## Tracing

Sentry still handles error reporting. OpenTelemetry tracing is intentionally not
part of this first metrics slice; it can be added later if request-level metrics
show a path that needs span-level attribution.
