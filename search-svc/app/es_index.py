from dataclasses import dataclass
from typing import Any, Protocol

from elastic_transport import TransportError
from elasticsearch import Elasticsearch, NotFoundError

# `files` points at `files-v1`. A future mapping change builds `files-v2` and
# swaps the alias, so reindexing never needs downtime (decision 10). The
# index is created *through* this alias from the start -- see ensure_index.
INDEX_ALIAS = "files"
INDEX_NAME = "files-v1"

# The standard analyzer splits `report_2024-final.pdf` in ways users find
# surprising. This char_filter turns separators into spaces before the
# standard tokenizer runs, so "report", "2024" and "final" all match
# (decision 14). Edge-ngram / search_as_you_type are deliberately not used
# yet -- nothing needs prefix completion until the UI asks for it.
INDEX_SETTINGS: dict[str, Any] = {
    # Single node for now (decision 3; clustering and replicas are out of
    # scope). The default of 1 replica can never be satisfied with only one
    # node, which leaves the cluster stuck yellow and makes every index
    # creation block for ~30s waiting on shard allocation before giving up.
    "index": {"number_of_replicas": 0},
    "analysis": {
        "char_filter": {
            "separator_to_space": {
                "type": "mapping",
                # Elasticsearch's mapping char filter trims a literal
                # trailing space in the target, silently turning "_ => " (a
                # single space) into a no-op removal instead of a
                # replacement. The unicode escape below is Elasticsearch's
                # own documented way to write a whitespace target
                # unambiguously -- confirmed against a real node via
                # _analyze; a bare trailing space concatenates the filename
                # into one token instead of splitting it.
                "mappings": ["_ => \\u0020", "- => \\u0020", ". => \\u0020"],
            }
        },
        "analyzer": {
            "filename_analyzer": {
                "type": "custom",
                "char_filter": ["separator_to_space"],
                "tokenizer": "standard",
                "filter": ["lowercase"],
            }
        },
    },
}

# Mirrors the Elasticsearch document id into an ordinary mapped field, purely
# so it can be a sort tiebreaker -- see _SORT_ID_FIELD below for why.
_SORT_ID_FIELD = "doc_id"

INDEX_MAPPINGS: dict[str, Any] = {
    "properties": {
        "owner_id": {"type": "keyword"},
        "name": {
            "type": "text",
            "analyzer": "filename_analyzer",
            "fields": {"raw": {"type": "keyword"}},
        },
        # A keyword, not text: search filters on it (decision 11), and a
        # future folder_renamed event applies one update_by_query against a
        # path prefix rather than rewriting documents one by one
        # (decision 12).
        "folder_path": {"type": "keyword"},
        "mime_type": {"type": "keyword"},
        "category": {"type": "keyword"},
        "size_bytes": {"type": "long"},
        "created_at": {"type": "date"},
        # Not part of the event contract or _FILE_CREATED_DOCUMENT_FIELDS in
        # app/indexer.py -- index_document() below writes it on every call,
        # mirroring the id it is already given. It exists solely so
        # SEARCH_SORT has a doc-values-backed tiebreaker: Elasticsearch
        # disables fielddata on the real `_id` field by default (loading
        # every document id into memory is expensive), so `sort: [{"_id":
        # "asc"}]` fails with a 400 asking to re-enable it cluster-wide.
        # Sorting on an ordinary keyword field avoids that entirely, at the
        # cost of one small field per document.
        _SORT_ID_FIELD: {"type": "keyword"},
    }
}


# Relevance first, recency as a tiebreaker, doc_id last so `search_after` has
# a deterministic total ordering -- without it, pagination silently
# duplicates or skips results whenever score and created_at tie (decision
# 16; see _SORT_ID_FIELD for why this is doc_id and not `_id` itself).
SEARCH_SORT: list[dict[str, Any]] = [
    {"_score": "desc"},
    {"created_at": "desc"},
    {_SORT_ID_FIELD: "asc"},
]


class SearchIndexUnavailableError(Exception):
    """Elasticsearch could not be reached. Maps to 503, never empty results

    (decision 15) -- an empty result set is indistinguishable from "no
    matches" and would hide an outage from users and operators alike.
    """


@dataclass(frozen=True)
class SearchHit:
    doc_id: str
    source: dict[str, Any]
    # The hit's raw Elasticsearch sort values, in SEARCH_SORT order. Passed
    # straight through to a future search_after -- see app/cursor.py.
    sort: list[Any]


def _folder_scope_predicate(folder_path: str) -> dict[str, Any]:
    """A folder and everything beneath it -- and nothing else.

    `folder_path` is a keyword, so a naive `prefix` query on "root.docs" would
    also match "root.docsarchive". Matching on the exact path OR a
    dot-terminated prefix is what keeps siblings out. This predicate is the
    single source of truth for "in this folder": search() and
    delete_by_folder_prefix() both call it, so they can never disagree about
    which documents belong to a folder (design doc constraint 2).
    """
    return {
        "bool": {
            "should": [
                {"term": {"folder_path": folder_path}},
                {"prefix": {"folder_path": f"{folder_path}."}},
            ],
            "minimum_should_match": 1,
        }
    }


def build_search_query(
    *,
    owner_id: str,
    folder_path: str,
    query: str | None,
    category: str | None,
) -> dict[str, Any]:
    """Build the query body. owner_id is always the first filter clause and

    always in filter context -- never in a scored ("must") clause -- so it is
    cacheable, unscored, and cannot be bypassed by any combination of the
    other arguments (design doc decision 6, the single ownership chokepoint).
    """
    filters: list[dict[str, Any]] = [
        {"term": {"owner_id": owner_id}},
        _folder_scope_predicate(folder_path),
    ]
    if category is not None:
        filters.append({"term": {"category": category}})

    must: dict[str, Any] = {"match": {"name": query}} if query else {"match_all": {}}

    return {"bool": {"filter": filters, "must": must}}


class SearchIndex(Protocol):
    def ensure_index(self) -> None: ...

    def index_document(self, *, doc_id: str, document: dict[str, Any]) -> None: ...

    def delete_document(self, *, doc_id: str) -> None: ...

    def delete_by_folder_prefix(self, *, owner_id: str, folder_path: str) -> None: ...

    def search(
        self,
        *,
        owner_id: str,
        folder_path: str,
        query: str | None,
        category: str | None,
        limit: int,
        search_after: list[Any] | None,
    ) -> list[SearchHit]: ...

    def is_healthy(self) -> bool: ...


class ElasticsearchIndex:
    def __init__(
        self,
        client: Elasticsearch,
        *,
        alias: str = INDEX_ALIAS,
        index_name: str = INDEX_NAME,
    ) -> None:
        self._client = client
        self._alias = alias
        self._index_name = index_name

    def ensure_index(self) -> None:
        if self._client.indices.exists(index=self._index_name):
            return
        self._client.indices.create(
            index=self._index_name,
            settings=INDEX_SETTINGS,
            mappings=INDEX_MAPPINGS,
            aliases={self._alias: {}},
        )

    def index_document(self, *, doc_id: str, document: dict[str, Any]) -> None:
        # Indexing by the file's own id is naturally idempotent: redelivery
        # overwrites the same document instead of creating a duplicate. The
        # mirrored _SORT_ID_FIELD is added here, not by callers -- it is a
        # sort-only implementation detail of this class, not part of what
        # app/indexer.py writes (see the mapping comment above).
        body = {**document, _SORT_ID_FIELD: doc_id}
        self._client.index(index=self._alias, id=doc_id, document=body)

    def delete_document(self, *, doc_id: str) -> None:
        try:
            self._client.delete(index=self._alias, id=doc_id)
        except NotFoundError:
            # Already deleted. Redelivery of file_deleted must not nack or
            # loop (design doc constraint 6) -- a 404 here means success.
            pass

    def delete_by_folder_prefix(self, *, owner_id: str, folder_path: str) -> None:
        self._client.delete_by_query(
            index=self._alias,
            query={
                "bool": {
                    "filter": [
                        {"term": {"owner_id": owner_id}},
                        _folder_scope_predicate(folder_path),
                    ]
                }
            },
            conflicts="proceed",
        )

    def search(
        self,
        *,
        owner_id: str,
        folder_path: str,
        query: str | None,
        category: str | None,
        limit: int,
        search_after: list[Any] | None,
    ) -> list[SearchHit]:
        try:
            response = self._client.search(
                index=self._alias,
                query=build_search_query(
                    owner_id=owner_id,
                    folder_path=folder_path,
                    query=query,
                    category=category,
                ),
                sort=SEARCH_SORT,
                size=limit,
                search_after=search_after,
            )
        except TransportError as exc:
            raise SearchIndexUnavailableError(str(exc)) from exc
        except NotFoundError:
            # The alias doesn't exist yet -- nothing has been indexed. This is
            # a genuinely empty result, not an outage.
            return []

        return [
            SearchHit(doc_id=hit["_id"], source=hit["_source"], sort=hit["sort"])
            for hit in response["hits"]["hits"]
        ]

    def is_healthy(self) -> bool:
        try:
            return bool(self._client.ping())
        except TransportError:
            return False
