import secrets
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from time import perf_counter

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

# Matches backend's app/core/metrics.py shape (design doc decision 18).
# search-svc has no database pool to instrument, so only HTTP and
# Elasticsearch operation metrics apply here.
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

SEARCH_QUERIES = Counter(
    "search_queries_total",
    "Elasticsearch queries issued by search-svc.",
    ("operation", "result"),
)
SEARCH_QUERY_DURATION = Histogram(
    "search_query_duration_seconds",
    "Elasticsearch query duration in seconds.",
    ("operation", "result"),
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


@contextmanager
def track_search_query(operation: str) -> Iterator[None]:
    start = perf_counter()
    result = "success"
    try:
        yield
    except Exception:
        result = "error"
        raise
    finally:
        duration = perf_counter() - start
        SEARCH_QUERIES.labels(operation=operation, result=result).inc()
        SEARCH_QUERY_DURATION.labels(operation=operation, result=result).observe(
            duration
        )


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
