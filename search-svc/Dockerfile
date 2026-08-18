FROM python:3.14.7-slim-trixie AS python-base

ENV PYTHONUNBUFFERED=1

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"


FROM python-base AS dependency-builder

# uv is required only to construct the virtual environment. The final runtime
# image receives the environment, not the package manager or its installation
# layer.
RUN pip install --no-cache-dir uv==0.9.26

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY ./search-svc/pyproject.toml ./search-svc/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python-base AS runtime

COPY --from=dependency-builder /app/.venv /app/.venv
COPY ./search-svc/app ./app

CMD ["fastapi", "run", "app/main.py"]
