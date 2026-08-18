from dataclasses import dataclass

from app.cursor import decode_cursor, encode_cursor
from app.es_index import SearchHit, SearchIndex


@dataclass(frozen=True)
class SearchResult:
    id: str
    name: str
    folder_path: str
    mime_type: str
    category: str
    size_bytes: int
    created_at: str


@dataclass(frozen=True)
class SearchPage:
    results: list[SearchResult]
    next_cursor: str | None


def _to_result(hit: SearchHit) -> SearchResult:
    # Mirrors indexer.py's _FILE_CREATED_DOCUMENT_FIELDS -- the fields the
    # indexer writes into a document are exactly the fields a result reads
    # back out, plus the id, which lives in Elasticsearch hit metadata rather
    # than _source (design doc constraint 3).
    source = hit.source
    return SearchResult(
        id=hit.doc_id,
        name=source["name"],
        folder_path=source["folder_path"],
        mime_type=source["mime_type"],
        category=source["category"],
        size_bytes=source["size_bytes"],
        created_at=source["created_at"],
    )


def execute_search(
    *,
    index: SearchIndex,
    owner_id: str,
    folder_path: str,
    q: str | None,
    category: str | None,
    limit: int,
    cursor: str | None,
) -> SearchPage:
    """Run one page of a search. owner_id must come from the verified token,

    never from the cursor (design doc constraint 5) -- the caller is
    responsible for that; this function just passes whatever owner_id it is
    given down to the single chokepoint inside SearchIndex.search.

    Fetches one extra hit beyond `limit` to decide whether a next page
    exists, without which a result set that is an exact multiple of `limit`
    could never be told apart from the true last page.
    """
    search_after = decode_cursor(cursor) if cursor is not None else None

    hits = index.search(
        owner_id=owner_id,
        folder_path=folder_path,
        query=q,
        category=category,
        limit=limit + 1,
        search_after=search_after,
    )

    has_more = len(hits) > limit
    page_hits = hits[:limit]

    next_cursor = encode_cursor(page_hits[-1].sort) if has_more and page_hits else None
    return SearchPage(
        results=[_to_result(hit) for hit in page_hits], next_cursor=next_cursor
    )
