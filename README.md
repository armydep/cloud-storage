# Cloud File Storage

Cloud File Storage is a web application for authenticated users to manage files
and folders in a private cloud-style workspace.

## Phase 1 scope

Phase 1 starts the file-management API.

- Add authenticated file endpoints.
- Add `GET /api/v1/files/root`.
- Create the user's root folder lazily on first page load.
- Return the same root folder and its contents on later page loads.
- Add backend tests for the endpoint.

## Current API

### `GET /api/v1/files/root`

Returns the authenticated user's root folder and its contents.

If the user does not have a root folder yet, the backend creates one and returns
it. This lets the frontend call the endpoint on page load without running a
separate setup flow.

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

Start the stack:

```bash
docker compose up -d
```

Useful local URLs:

```text
Frontend:       http://localhost:5173
Backend API:    http://localhost:8000
Swagger UI:     http://localhost:8000/docs
OpenAPI JSON:   http://localhost:8000/api/v1/openapi.json
Adminer:        http://localhost:8080
Mailcatcher:    http://localhost:1080
Traefik:        http://localhost:8090
```

Run backend database migrations:

```bash
docker compose exec backend alembic upgrade head
```

Run backend tests:

```bash
docker compose exec backend bash scripts/test.sh
```

## Environment files

Local `.env` files are intentionally ignored by Git. Keep secrets and local
credentials there, not in committed source files.

Ignored local files include:

```text
.env
frontend/.env
.copier/.copier-answers.yml
.idea/
```

## Tech stack

- FastAPI backend
- PostgreSQL database
- SQLModel and Alembic
- React frontend
- Docker Compose for local development
- Traefik reverse proxy
