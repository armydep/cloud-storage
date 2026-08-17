FROM python:3.14

ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv==0.9.26

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

COPY ./search-svc/pyproject.toml ./search-svc/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY ./search-svc/app ./app

CMD ["fastapi", "run", "app/main.py"]
