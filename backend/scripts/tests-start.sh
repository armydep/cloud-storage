#! /usr/bin/env bash
set -e
set -x

# No database readiness wait here: the tests start their own PostgreSQL
# container (backend/conftest.py) and testcontainers blocks until it is ready.
bash scripts/test.sh "$@"
