#! /usr/bin/env bash

set -e
set -x

cd backend
uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ../openapi.json
cd ..
cd search-svc
uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ../search-openapi.json
cd ..
mv openapi.json frontend/
mv search-openapi.json frontend/
bun run --filter frontend generate-client
cd frontend
bun x openapi-ts --file openapi-search-ts.config.ts
cd ..
find frontend/src/client frontend/src/search-client -type f -name "*.ts" -exec sed -i 's/[[:space:]]*$//' {} +
bun run lint
