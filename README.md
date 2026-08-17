# Cloud File Storage

Cloud File Storage is a web application for authenticated users to manage files
and folders in a private cloud-style workspace.

Feature designs:

- [File sharing with specific users](docs/phases/phase-4-file-sharing.md)
- [Delete files with deduplicated blob storage](docs/phases/phase-6-delete-file.md)
- [Delete folders recursively](docs/phases/phase-7-delete-folder.md)
- [Backend scaling configuration](docs/backend-scaling.md)

## Phase 1 scope

Phase 1 starts the file-management API.

- Add authenticated file endpoints.
- Add `GET /api/v1/files?path=<ltree-path>`.
- Create the user's root folder lazily on first page load.
- Return the same root folder and its contents on later page loads.
- Add backend tests for the endpoint.

## Current API

### `GET /api/v1/files?path=<ltree-path>`

Returns the requested folder and its direct contents.

If `path` is omitted, it defaults to `root`. If the user does not have a root
folder yet, the backend creates one and returns it. Other missing paths return
`404`.

Example response:

```json
{
  "id": "9f23b079-4d95-46cb-b57d-7430118b1d6e",
  "owner_id": "0ce5d6d4-6d65-4032-8571-c560b03b5310",
  "parent_id": null,
  "path": "root",
  "name": "root",
  "contents": [
    {
      "id": "d9d07d65-8f99-40c5-b6e2-48f931a09e63",
      "name": "report.pdf",
      "type": "file",
      "mime_type": "application/pdf",
      "category": "document",
      "blob_hash": "abc123",
      "size_bytes": 12345
    }
  ]
}
```

Authentication is required. Callers must send a bearer token:

```text
Authorization: Bearer <access-token>
```

## Local development

Create your local `.env` first. The stack does not start without it, because
Docker Compose and the backend settings both read values from it:

```bash
cp .env.example .env
```

Start the stack:

```bash
docker compose up -d
```

Useful local URLs:

```text
Frontend:       http://localhost:5173
API gateway:    http://api.localhost
Backend direct: http://localhost:8000
Backend docs:   http://localhost:8000/docs
Search docs:    http://api.localhost/api/v1/search/docs
Metrics:        http://localhost:8000/metrics
Adminer:        http://localhost:8080
Mailcatcher:    http://localhost:1080
Traefik:        http://localhost:8090
MinIO S3 API:   http://localhost:9000
MinIO console:  http://localhost:9001
```

The local frontend is built with `VITE_API_URL=http://api.localhost`, so its API
requests enter through Traefik and `/api/v1/search/*` follows the same routing as
production. All other API paths continue to reach `backend`. Port 8000 is kept
published only for direct backend debugging.

### Android application

The Android-only Flutter client lives in `mobile/`, independently from the
React application in `frontend/`. It supports the core authenticated file
management workflow. Full device synchronization is not implemented yet.

See [`mobile/README.md`](mobile/README.md) for Flutter prerequisites, API URL
configuration, and run, build, analysis, and test commands.

Run backend database migrations:

```bash
docker compose exec backend alembic upgrade head
```

Run backend tests:

```bash
docker compose exec backend bash scripts/test.sh
```

Backend metrics are available in Prometheus format when
`METRICS_BEARER_TOKEN` is configured. See
[`docs/observability.md`](docs/observability.md) for the endpoint, scrape
configuration, and the database pool signals to inspect before changing
connection limits.

## Environment files

`.env.example` is committed and holds non-secret defaults. Copy it to `.env`
and edit that copy; `.env` itself is ignored by Git, so keep secrets and local
credentials there, not in committed source files.

Values set to `changethis` must be replaced for any real deployment. The
backend only warns about them when `ENVIRONMENT=local` and refuses to start
otherwise.

Ignored local files include:

```text
.env
frontend/.env
.copier/.copier-answers.yml
.idea/
```

## Tech stack

- FastAPI backend
- Independently deployable FastAPI search service
- PostgreSQL database
- SQLModel and Alembic
- React frontend
- Flutter Android application
- Docker Compose for local development
- Traefik reverse proxy
