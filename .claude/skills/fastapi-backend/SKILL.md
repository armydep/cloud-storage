---
name: fastapi-backend
description: >
  Structure and conventions for the cloud-storage FastAPI backend. Use whenever
  creating or modifying backend code under backend/ — adding a route, service,
  repository, model, schema, Alembic migration, config, or test — so new code follows
  the project's feature-first layering, ownership scoping, storage rules, migration
  discipline, and testing conventions.
---

# cloud-storage backend conventions

FastAPI, SQLModel, Alembic, PostgreSQL 18 (with `ltree`), psycopg 3, boto3 against
S3-compatible storage (MinIO locally), JWT auth, pytest. Module root: `backend/`.
Base package: `app`. Dependencies and tooling via `uv`.

`ROADMAP.md` is authoritative for what gets built; `docs/scalability-review.md`
records known structural weaknesses. This skill is the *how we build it* layer.

## Package layout

The `files` feature is feature-first with layers inside it. The template's
original `users`/`login` routes remain in the older flat layout — follow
the `files` pattern for anything new.

```
app
├── main.py
├── api/
│   ├── deps.py              SessionDep, CurrentUser, get_current_active_superuser
│   ├── main.py              router aggregation
│   └── routes/              HTTP layer only — one module per feature
├── core/
│   ├── config.py            pydantic-settings; every env var declared here
│   ├── db.py                engine + init_db
│   ├── security.py          JWT, password hashing
│   └── storage.py           the single seam over S3/MinIO
├── files/                   the feature-first example to follow
│   ├── models.py            SQLModel tables + LtreeType
│   ├── schemas.py           API contracts, validators, LTREE_PATH_PATTERN
│   ├── repository.py        all SQL for the feature
│   └── service.py           business logic + domain exceptions
├── models.py                User and authentication schemas (template-era, shared)
├── crud.py                  user CRUD (template-era)
└── alembic/versions/        migrations
```

Rules:
- **Dependencies point inward:** `api/routes` → `service` → `repository` → `models`.
  Routes never build queries. Repositories never raise `HTTPException`.
- A feature owns its modules; create only the layers it needs.
- Cross-feature reuse goes through a service function, not by importing another
  feature's repository.

## Layer responsibilities

- **routes:** thin. Parse and validate input, call one service function, map domain
  exceptions to `HTTPException`. This is the *only* layer that knows HTTP status
  codes. Declare `response_model` on every endpoint so the OpenAPI schema — and
  therefore the generated frontend client — stays accurate.
- **service:** business logic. Raises domain exceptions (`FolderNotFoundError`,
  `DuplicateFileNameError`, `ObjectNotUploadedError`). Never imports FastAPI.
- **repository:** every `select`/`insert`/`update`. Returns models or `None`.
  Handles `IntegrityError` where a constraint is the intended control flow (see
  `create_root_folder`).
- **models:** SQLModel tables. Indexes and constraints declared in `__table_args__`.
- **schemas:** request/response shapes and field validators. Public response models
  never expose anything the caller should not see.

## Ownership and access — the rule that matters most

Every file and folder belongs to exactly one user. There is no sharing yet.

- **Every repository query filters on `owner_id`.** Fetching by primary key alone
  is a bug, even when a service check follows it.
- **Cross-user access returns 404, never 403.** Revealing that a resource exists is
  itself a leak.
- Ownership comes from the `CurrentUser` dependency — never from a request body or
  query parameter.

## Object storage

- All object access goes through `app/core/storage.py`. Nothing else imports boto3.
- **Presigned URLs only.** Never stream file bytes through a route: the API must not
  become a bandwidth bottleneck.
- Object keys are content-addressed (`sha256/<hash>`), so **one object can back many
  `files` rows** — the same content uploaded to two folders is one object. Two
  consequences:
  - A delete path must not call `delete_object` until reclamation exists.
  - Anything that accepts a client-supplied key or hash must verify the caller
    actually uploaded that object.
  See `docs/scalability-review.md` section 8.
- `S3_ENDPOINT_URL` is the in-network address; `S3_PUBLIC_ENDPOINT_URL` is what the
  browser reaches. `_rewrite_public_url` bridges them — presigned URLs handed to a
  client must always go through it.

## Migrations

- **Alembic only.** Never let SQLModel create tables; `init_db` leaves `create_all`
  commented out deliberately.
- **One head, always.** Run `uv run alembic heads` first and set `down_revision` to
  it. Two migrations sharing a `down_revision` produce multiple heads and
  `alembic upgrade head` fails outright. This has happened in this repo.
- Never edit an applied migration; add a new one.
- File-storage migrations use raw `op.execute` with `IF NOT EXISTS` — match the
  surrounding file's style rather than mixing idioms.
- Every index or constraint added in a migration must also appear in the model's
  `__table_args__`, or autogenerate reports drift forever.
- ltree columns need a **GiST** index for subtree queries; plain btree does not
  serve `@>` / `<@`.
- Verify a migration by running it forward *and* backward against a scratch
  database before committing.

## Validation

- Paths reaching an ltree column must match `LTREE_PATH_PATTERN` **before** they
  reach SQL. Unvalidated input arrives at Postgres as raw ltree and raises
  `psycopg.errors.SyntaxError`, which surfaces as a 500 rather than a 422.
- Put constraints on `Query(...)` and `Field(...)`, not in hand-rolled checks, so
  they appear in the OpenAPI schema and propagate to the generated client.
- `LtreeType.bind_expression` casts parameters explicitly (`CAST(:p AS LTREE)`)
  rather than relying on Postgres inferring the type from context.

## Pagination

New list endpoints take `skip`/`limit` (see `api/routes/users.py`). The folder
listing currently has none — that is a known gap (`SCALE 1.1`–`1.4`), not a
pattern to copy.

## Configuration

- Every environment variable is declared in `core/config.py` with a default where
  one is safe. Secrets default to `changethis`, which the settings validator warns
  about locally and rejects outside `local`.
- New variables go in `.env.example` in the same change.
- `.env` is required and untracked: `cp .env.example .env`.

## Testing

- Real PostgreSQL with `ltree`. No SQLite fallback, no mocking the database.
- The `db` fixture wipes tables on teardown, but only when the database name
  contains `test` (`_is_test_database`). Point `POSTGRES_DB` at a throwaway
  database; running against a dev database leaves rows behind.
- Object storage is monkeypatched at the `app.files.service.storage` boundary
  (see `test_files.py`) — tests never call MinIO.
- Every new endpoint needs at least: happy path, unauthenticated (401), and another
  user's resource (404).
- Coverage is gated at 90%.

## Typing and style

- mypy runs `strict`. There is a pre-existing failure baseline in
  `api/routes/users.py` — do not add to it, and do not fix it as a
  drive-by.
- ruff for lint and format: `uv run bash scripts/lint.sh` checks,
  `uv run bash scripts/format.sh` fixes.
- Sizes are `BigInteger`; timestamps are `timestamptz` in UTC via
  `get_datetime_utc`.

## Build / run

From `backend/`: `uv run fastapi dev app/main.py`, `uv run pytest tests/ -q`,
`uv run alembic upgrade head`, `uv run bash scripts/lint.sh`.
Stack from the repo root: `docker compose watch`.

After changing any request or response model, regenerate the frontend client from
the repo root: `bash scripts/generate-client.sh`.
