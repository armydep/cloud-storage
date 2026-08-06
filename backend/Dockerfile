FROM python:3.14

ENV PYTHONUNBUFFERED=1

# Optional, inert unless explicitly invoked: some sandboxed CI/dev environments
# intercept outbound TLS with their own CA, which pypi.org does not trust by
# default, and pip install fails with SELF_SIGNED_CERT_IN_CHAIN. Passing
# --secret id=sandbox_ca,src=<path-to-that-CA> installs it for this build
# only; without it (every normal build, including CI) this is a no-op since
# it points at the system's own default trust store.
RUN --mount=type=secret,id=sandbox_ca,required=false \
    if [ -s /run/secrets/sandbox_ca ]; then \
      cp /run/secrets/sandbox_ca /usr/local/share/ca-certificates/sandbox-ca.crt && \
      update-ca-certificates; \
    fi
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
RUN pip install --no-cache-dir uv==0.9.26

# Compile bytecode
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

WORKDIR /app/

# Place executables in the environment at the front of the path
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV PATH="/app/.venv/bin:$PATH"

# Install dependencies
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-workspace --package app

COPY ./backend/scripts /app/backend/scripts

COPY ./backend/pyproject.toml ./backend/alembic.ini /app/backend/

COPY ./backend/app /app/backend/app

# Sync the project
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --package app

WORKDIR /app/backend/

CMD ["fastapi", "run", "--workers", "4", "app/main.py"]
