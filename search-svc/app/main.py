from typing import Annotated

from fastapi import APIRouter, FastAPI, Query
from starlette.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas import (
    LTREE_PATH_PATTERN,
    FileCategory,
    HealthResponse,
    SearchResponse,
)
from app.security import CurrentSubject

search_router = APIRouter(prefix="/search", tags=["search"])


@search_router.get("/files", response_model=SearchResponse)
def search_files(
    current_subject: CurrentSubject,
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
    """Return the empty slice-1 search result contract."""
    _ = current_subject, folder_path, q, category, limit, cursor
    return SearchResponse()


@search_router.get("/health", response_model=HealthResponse)
def health_check(current_subject: CurrentSubject) -> HealthResponse:
    _ = current_subject
    return HealthResponse(status="ok", index="files", engine="elasticsearch")


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

app.include_router(search_router, prefix=settings.API_V1_STR)
