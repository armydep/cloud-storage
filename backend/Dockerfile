FROM python:3.14.7-slim-trixie AS python-base

ENV PYTHONUNBUFFERED=1

ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app/

# Place executables in the environment at the front of the path.
ENV PATH="/app/.venv/bin:$PATH"


FROM python-base AS dependency-builder

# Some sandboxed CI/dev environments intercept outbound TLS with their own CA.
# Keep that optional trust material in this discarded build stage, and require
# its SHA-256 as an explicit cache key because BuildKit secret contents do not
# invalidate cached layers. Normal builds supply neither value.
ARG SANDBOX_CA_SHA256=""
RUN --mount=type=secret,id=sandbox_ca,required=false \
    if [ -s /run/secrets/sandbox_ca ]; then \
      test -n "$SANDBOX_CA_SHA256" || \
        (echo "SANDBOX_CA_SHA256 is required with sandbox_ca" >&2; exit 1); \
      printf '%s  %s\n' "$SANDBOX_CA_SHA256" /run/secrets/sandbox_ca | sha256sum -c -; \
      cp /run/secrets/sandbox_ca /usr/local/share/ca-certificates/sandbox-ca.crt; \
      update-ca-certificates; \
    elif [ -n "$SANDBOX_CA_SHA256" ]; then \
      echo "sandbox_ca is required with SANDBOX_CA_SHA256" >&2; \
      exit 1; \
    fi

# uv is build tooling, not an application runtime dependency. Keeping it in
# this discarded stage avoids adding the installer and uv itself to the final
# image while preserving the existing cache-mounted sync workflow.
RUN pip install --no-cache-dir uv==0.9.26

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install runtime dependencies before copying the application so ordinary code
# edits reuse this expensive layer. The second sync installs the workspace
# package after its source is present.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-workspace --package app

COPY ./backend/scripts /app/backend/scripts
COPY ./backend/pyproject.toml ./backend/alembic.ini /app/backend/
COPY ./backend/app /app/backend/app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --package app


FROM dependency-builder AS development-dependencies

# Local containerized tests intentionally need the development dependency
# group. compose.override.yml selects the matching development image target;
# production never inherits this stage.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --package app


FROM python-base AS application

# The Compose healthcheck intentionally remains curl-based. Install only that
# runtime utility; the compilers and general build toolchain from the full
# Python image are no longer present.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY ./backend/scripts /app/backend/scripts
COPY ./backend/pyproject.toml ./backend/alembic.ini /app/backend/
COPY ./backend/app /app/backend/app

WORKDIR /app/backend/

CMD ["sh", "-c", "exec fastapi run --workers ${BACKEND_WORKERS:-4} app/main.py"]


FROM application AS development

COPY --from=development-dependencies /app/.venv /app/.venv


# Keep the production stage last so a build without --target always emits the
# runtime-only image. All backend-derived services share one image tag, while
# compose.override.yml consistently selects `development` for local use.
FROM application AS runtime

COPY --from=dependency-builder /app/.venv /app/.venv
