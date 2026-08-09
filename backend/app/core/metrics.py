import secrets
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests.",
    ("method", "endpoint", "status_code"),
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "endpoint"),
)

DB_POOL_CHECKED_OUT = Gauge(
    "db_pool_checked_out_connections",
    "Currently checked-out database connections.",
    ("pool",),
)
DB_POOL_CHECKED_IN = Gauge(
    "db_pool_checked_in_connections",
    "Currently checked-in database connections.",
    ("pool",),
)
DB_POOL_SIZE = Gauge(
    "db_pool_size_connections",
    "Configured SQLAlchemy database pool size.",
    ("pool",),
)
DB_POOL_OVERFLOW = Gauge(
    "db_pool_overflow_connections",
    "Current SQLAlchemy database pool overflow connection count.",
    ("pool",),
)
DB_POOL_CHECKOUT_WAIT = Histogram(
    "db_pool_checkout_wait_seconds",
    "Time spent waiting for a database connection checkout.",
    ("pool",),
)
DB_POOL_EVENTS = Counter(
    "db_pool_events_total",
    "Database connection pool events.",
    ("pool", "event"),
)

OBJECT_STORAGE_OPERATIONS = Counter(
    "object_storage_operations_total",
    "Object-storage operations.",
    ("operation", "result"),
)
OBJECT_STORAGE_OPERATION_DURATION = Histogram(
    "object_storage_operation_duration_seconds",
    "Object-storage operation duration in seconds.",
    ("operation", "result"),
)

POOL_LABEL = "default"


class InstrumentedQueuePool(QueuePool):
    def _do_get(self) -> Any:
        start = perf_counter()
        try:
            return super()._do_get()
        finally:
            DB_POOL_CHECKOUT_WAIT.labels(pool=POOL_LABEL).observe(
                perf_counter() - start
            )


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            endpoint = _get_endpoint_label(request)
            method = request.method
            duration = perf_counter() - start
            HTTP_REQUESTS.labels(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code),
            ).inc()
            HTTP_REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint,
            ).observe(duration)


def install_metrics(app: FastAPI) -> None:
    app.add_middleware(RequestMetricsMiddleware)
    app.add_api_route(
        "/metrics",
        metrics_endpoint,
        methods=["GET"],
        include_in_schema=False,
        tags=["metrics"],
    )


def metrics_endpoint(authorization: str | None = Header(default=None)) -> Response:
    _verify_metrics_authorization(authorization)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def instrument_sqlalchemy_pool(engine: Engine) -> None:
    _update_pool_gauges(engine)

    @event.listens_for(engine.pool, "connect")
    def _record_connect(*_args: Any, **_kwargs: Any) -> None:
        DB_POOL_EVENTS.labels(pool=POOL_LABEL, event="connect").inc()
        _update_pool_gauges(engine)

    @event.listens_for(engine.pool, "close")
    def _record_close(*_args: Any, **_kwargs: Any) -> None:
        DB_POOL_EVENTS.labels(pool=POOL_LABEL, event="close").inc()
        _update_pool_gauges(engine)

    @event.listens_for(engine.pool, "checkout")
    def _record_checkout(*_args: Any, **_kwargs: Any) -> None:
        DB_POOL_EVENTS.labels(pool=POOL_LABEL, event="checkout").inc()
        _update_pool_gauges(engine)

    @event.listens_for(engine.pool, "checkin")
    def _record_checkin(*_args: Any, **_kwargs: Any) -> None:
        DB_POOL_EVENTS.labels(pool=POOL_LABEL, event="checkin").inc()
        _update_pool_gauges(engine)


@contextmanager
def track_object_storage_operation(operation: str) -> Iterator[None]:
    start = perf_counter()
    result = "success"
    try:
        yield
    except Exception:
        result = "error"
        raise
    finally:
        duration = perf_counter() - start
        OBJECT_STORAGE_OPERATIONS.labels(operation=operation, result=result).inc()
        OBJECT_STORAGE_OPERATION_DURATION.labels(
            operation=operation,
            result=result,
        ).observe(duration)


def _verify_metrics_authorization(authorization: str | None) -> None:
    token = settings.METRICS_BEARER_TOKEN
    if not token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided_token = authorization.removeprefix(prefix)
    if not secrets.compare_digest(provided_token, token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


def _get_endpoint_label(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str):
        return route_path
    return "unmatched"


def _update_pool_gauges(engine: Engine) -> None:
    pool = engine.pool
    if not isinstance(pool, QueuePool):
        return

    DB_POOL_CHECKED_OUT.labels(pool=POOL_LABEL).set(pool.checkedout())
    DB_POOL_CHECKED_IN.labels(pool=POOL_LABEL).set(pool.checkedin())
    DB_POOL_SIZE.labels(pool=POOL_LABEL).set(pool.size())
    DB_POOL_OVERFLOW.labels(pool=POOL_LABEL).set(pool.overflow())
