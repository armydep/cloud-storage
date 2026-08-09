#!/usr/bin/env bash
# Run the Playwright suite locally in a disposable Docker Compose project,
# separate from a developer's own `docker compose watch` stack.
#
# Without this, `bunx playwright test` reuses whatever is already serving
# http://localhost:5173 (Playwright's `reuseExistingServer: !CI`), which
# locally is the developer's own frontend, backend and database. Six of the
# eight spec files are not mocked and hit that backend for real; one of them
# (user-settings.spec.ts) rewrites the superuser's own email and password.
#
# `-p` alone separates containers, volumes and networks, but not host port
# publishing — compose.e2e.yml resets the ports that would otherwise collide
# with an already-running dev stack. See that file for why this is safe: the
# playwright container never needs the host, only the compose-internal
# network.
#
# Usage: scripts/test-e2e-local.sh [playwright args...]
#   scripts/test-e2e-local.sh                       # full suite
#   scripts/test-e2e-local.sh tests/login.spec.ts    # a single spec

set -e

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Missing .env — run: cp .env.example .env" >&2
  exit 1
fi

PROJECT_NAME="cfs-e2e"
COMPOSE=(docker compose -p "$PROJECT_NAME" -f compose.yml -f compose.override.yml -f compose.e2e.yml)

cleanup() {
  "${COMPOSE[@]}" down -v --remove-orphans
}
trap cleanup EXIT

# Clears anything left behind by a previous run that crashed before the trap
# above could run. Safe against the dev stack: distinct project name.
"${COMPOSE[@]}" down -v --remove-orphans
"${COMPOSE[@]}" build
"${COMPOSE[@]}" run --rm playwright bunx playwright test "$@"
