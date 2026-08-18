from typing import Annotated

from elasticsearch import Elasticsearch
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from starlette.middleware.cors import CORSMiddleware

from app.config import settings
from app.cursor import InvalidCursorError
from app.es_index import (
    INDEX_ALIAS,
    ElasticsearchIndex,
    SearchIndex,
    SearchIndexUnavailableError,
)
from app.metrics import install_metrics, track_search_query
from app.schemas import (
    LTREE_PATH_PATTERN,
    FileCategory,
    HealthResponse,
    SearchResponse,
    SearchResultItem,
)
from app.search_service import execute_search
from app.security import CurrentSubject

search_router = APIRouter(prefix="/search", tags=["search"])

# One client, one index wrapper, shared across requests -- mirrors how
# indexer.py constructs its own. Connecting is lazy: building this doesn't
# touch the network, so it costs nothing at import time (tests import this
# module without Elasticsearch running).
_search_index: SearchIndex = ElasticsearchIndex(
    Elasticsearch(settings.ELASTICSEARCH_URL)
)


def get_search_index() -> SearchIndex:
    return _search_index


SearchIndexDep = Annotated[SearchIndex, Depends(get_search_index)]


@search_router.get("/files", response_model=SearchResponse)
def search_files(
    current_subject: CurrentSubject,
    index: SearchIndexDep,
    folder_path: Annotated[
        str,
        Query(
            min_length=1,
            max_length=1024,
            pattern=LTREE_PATH_PATTERN.pattern,
        ),
    ],
    q: Annotated[str | None, Query()] = None,
    category: Annotated[FileCategory | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> SearchResponse:
    try:
        with track_search_query("search"):
            page = execute_search(
                index=index,
                owner_id=current_subject,
                folder_path=folder_path,
                q=q,
                category=category.value if category is not None else None,
                limit=limit,
                cursor=cursor,
            )
    except InvalidCursorError:
        # A malformed or forged cursor must never reach the query builder,
        # mirroring the backend rule that an unvalidated ltree path never
        # reaches the datastore (design doc constraint 5).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid cursor",
        ) from None
    except SearchIndexUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search index unavailable",
        ) from None

    return SearchResponse(
        # SearchResult keeps id/category/created_at as plain strings -- the
        # shapes Elasticsearch and JSON actually carry -- and pydantic
        # validates and coerces them into UUID/FileCategory/datetime here, at
        # the API boundary where a malformed value should surface as a clear
        # response-model error rather than an assumption made earlier.
        results=[
            SearchResultItem.model_validate(result, from_attributes=True)
            for result in page.results
        ],
        next_cursor=page.next_cursor,
    )


@search_router.get("/health", response_model=HealthResponse)
def health_check(
    current_subject: CurrentSubject, index: SearchIndexDep
) -> HealthResponse:
    _ = current_subject
    with track_search_query("health"):
        healthy = index.is_healthy()
    if not healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search index unavailable",
        )
    return HealthResponse(status="ok", index=INDEX_ALIAS, engine="elasticsearch")


app = FastAPI(
    title="Cloud File Storage Search",
    openapi_url=f"{settings.API_V1_STR}/search/openapi.json",
    docs_url=f"{settings.API_V1_STR}/search/docs",
)

if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

install_metrics(app)
app.include_router(search_router, prefix=settings.API_V1_STR)
