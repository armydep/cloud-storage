# cloud-storage

Cloud File Storage: a FastAPI backend plus a React SPA, giving each authenticated user a private,
folder-structured workspace for files. Folder hierarchy is stored in Postgres as ltree materialized
paths; file bytes live in S3-compatible object storage (MinIO locally). **File bytes never pass
through the API** — the backend authenticates, checks ownership, and issues short-lived presigned
URLs so the browser transfers directly to and from object storage. Every file and folder is owned by
exactly one user; there is no sharing yet.

## Context docs (read these first)
@ROADMAP.md
@docs/project-management.md
@docs/scalability-review.md

`ROADMAP.md` is the product source of truth and numbers every outcome. The other two are how we work
and where the known structural weaknesses are.

Detailed design: `docs/phases/`. Flow diagrams: `docs/diagrams/`.

### Referring to numbered items
`ROADMAP.md` and `docs/scalability-review.md` both number items and **collide** (`8.2` means
different things in each). Always prefix: `ROADMAP 1.4`, `SCALE 8.2`, `#40` for issues.

## Layout
- `backend/` — FastAPI app (package root `app`, feature-first under `app/files/`).
- `frontend/` — React 19 + Vite + TypeScript SPA.
- `mobile/` — Android-only Flutter application.
- `compose.yml` + `compose.override.yml` — Postgres 18, MinIO, mailcatcher, Traefik, adminer.

## Build / test / run
`.env` is **required and untracked** — `cp .env.example .env` before anything else. Compose
interpolates from it and the backend settings read it; without it every command fails with
`Variable not set` or a Pydantic `Field required` error.

Stack: `docker compose watch` (or `docker compose up -d`) from the repo root.

Backend, from `backend/`:
- Tests for the backend-test-runner subagent: `uv run bash scripts/tests-start.sh`
  (needs Docker — the suite starts its own Postgres container; CI gates coverage at 90%).
- Single test: `uv run pytest tests/api/routes/test_files.py::test_name -q`.
- Lint: `uv run bash scripts/lint.sh` (mypy, ruff check, ruff format --check).
- Format: `uv run bash scripts/format.sh`.
- Migrate: `uv run alembic upgrade head`.

Frontend, from `frontend/`:
- Dev server: `bun run dev`. Lint: `bun run lint`. Build: `bun run build` (tsc **then** vite).
- E2E: `bunx playwright test` (needs the stack running).

Mobile, from `mobile/`:
- Dependencies: `flutter pub get`. Format check: `dart format --output=none --set-exit-if-changed .`.
- Analyze: `flutter analyze`. Test: `flutter test`.
- Run against the emulator host: `flutter run` (defaults to `http://10.0.2.2:8000`).

Client generation, from the repo root: `bash scripts/generate-client.sh`.

## Workflow
- Never run the test suites in the main session — delegate to the backend-test-runner and
  frontend-test-runner subagents.
- Before pushing a completed slice, delegate to the code-reviewer subagent and resolve every
  CRITICAL finding.
- One item in progress at a time; see `docs/project-management.md`.

## Handling reviewer output
Applies to code-reviewer-backend and code-reviewer-flutter alike.

Print the report verbatim. Never summarise or omit findings. Then:
- CRITICAL — fix immediately, state what changed for each.
- WARNING — list numbered, wait for one batched decision.
- NOTE — log only.

If a finding looks wrong, say so and don't fix it. Re-run the matching test-runner subagent after
any fixes.

## Test-runner subagents
Both test-runner agents follow the same contract: report failures only, cap output at 40 lines,
never modify files, never include raw tool output.

## CI parity
Before pushing, both test-runner subagents must pass. They mirror the workflows:
- backend — `.github/workflows/test-backend.yml`: `uv run bash scripts/tests-start.sh`, then
  coverage `--fail-under=90`
- frontend — `.github/workflows/playwright.yml`: `bun ci`, `bash scripts/generate-client.sh`,
  then Playwright via compose
- both — `.github/workflows/pre-commit.yml` runs `prek` over everything, which includes the
  generate-client hook

A subagent pass means CI should pass. If CI fails after both subagents passed, the agent definitions
have drifted from the workflows — fix the agent, not just the immediate failure.

## Conventions

### Schema and migrations
- Schema is Alembic-only. Never let SQLModel create tables (`init_db` deliberately leaves
  `create_all` commented out).
- **One head, always.** Before writing a migration, run `uv run alembic heads`; set
  `down_revision` to the current head. Two migrations sharing a `down_revision` produce multiple
  heads and `alembic upgrade head` fails outright — this has happened here before.
- Never edit an applied migration. File-storage migrations use raw `op.execute` SQL with
  `IF NOT EXISTS`; follow the surrounding file's style.
- Mirror every index and constraint in the model's `__table_args__` so autogenerate reports no
  drift.

### Backend structure
- Feature-first under `app/files/`: `models` (SQLModel tables) → `schemas` (API contracts,
  validators) → `repository` (all SQL) → `service` (business logic, domain exceptions).
- Dependencies point inward: `api/routes` → `service` → `repository` → `models`. Routes never
  build queries; repositories never raise HTTP errors.
- Services raise domain exceptions (`FolderNotFoundError`, `DuplicateFileNameError`); the route
  layer is the only place that maps them to `HTTPException`.
- Cross-user access returns **404**, never 403 — every repository query filters on `owner_id`.
- Ownership scoping goes through the `CurrentUser` dependency on every file and folder operation.

### Storage
- All object access goes through `app/core/storage.py`. Presigned URLs only — never stream file
  bytes through a FastAPI route.
- Object keys are content-addressed (`sha256/<hash>`), so **one object can back several `files`
  rows**. Deleting a file must not delete the object until reclamation exists; see
  `docs/scalability-review.md` section 8.

### Validation
- ltree paths are validated against `LTREE_PATH_PATTERN` before reaching SQL — an unvalidated path
  reaches Postgres as raw ltree and surfaces as a 500, not a 422.
- Query parameters get their constraints on `Query(...)` so they land in the OpenAPI schema and
  therefore in the generated client.

### Frontend
- `frontend/src/client/` and `frontend/src/search-client/` are **generated** — never hand-edit
  either. Change the backend or search service, then run `bash scripts/generate-client.sh`.
  Hand-editing generated clients has silently desynced the schemas here before.
- `bun`, never `npm` — the lockfile is `bun.lock`. There is no `package-lock.json`.
- E2E is Playwright; there is no Vitest in this project.
- `@playwright/test` in `package.json` must match the image tag in `frontend/Dockerfile.playwright`,
  or Playwright cannot find its browsers.
- `bunx playwright test` reuses whatever is already serving `localhost:5173` — locally that's your
  own `docker compose watch` stack. `files.spec.ts`, `shared-files.spec.ts`, and `search.spec.ts`
  mock their feature APIs and are safe to run individually that way. Specs that create arbitrary
  users against the real backend pollute your dev database. Use `bun run test:e2e` (from
  `frontend/`) for those, or for the full suite — it runs Playwright in a disposable
  `docker compose -p cfs-e2e` project via `scripts/test-e2e-local.sh`, so it never touches the dev
  stack or its database. CI is unaffected either way: each run gets a fresh runner and the workflow
  wraps itself in `docker compose down -v`.

### Testing
- Tests need a real Postgres with the `ltree` extension; there is no SQLite fallback. They start
  their own: `tests/container.py` boots a throwaway `postgres:18` via testcontainers, so **Docker
  must be running** and your own database is never touched. Nothing in `.env` configures the test
  database — the plugin overrides `POSTGRES_*` in the environment, which outranks `.env`.
- That has to be a plugin (`addopts = "-p tests.container"`), not a `conftest.py`. `app/core/db.py`
  builds its engine at import time, and pytest loads `tests/conftest.py` before any
  `pytest_configure` hook runs, so `pytest_load_initial_conftests` is the only hook early enough.
- The schema comes from `alembic upgrade head` against the container, never `create_all`, so every
  run exercises the real migration chain.
- `reset_database` truncates every table between test **modules** and re-seeds the superuser. It is
  per-module rather than per-test because `client`, `superuser_token_headers` and
  `normal_user_token_headers` are module-scoped and cache a logged-in user.
- Coverage gate is 90%.

### General
- mypy runs `strict`. It has a pre-existing baseline of failures in `app/api/routes/users.py`; do
  not add new ones, and do not "fix" the baseline as a drive-by.
- Money-free, but sizes are `BigInteger`; timestamps are `timestamptz`, UTC, via `get_datetime_utc`.
- Keep `ROADMAP.md` and the docs above in sync when behaviour changes; they are the source of truth.
