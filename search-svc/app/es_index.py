from typing import Any, Protocol

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
    }
}


class SearchIndex(Protocol):
    def ensure_index(self) -> None: ...

    def index_document(self, *, doc_id: str, document: dict[str, Any]) -> None: ...

    def delete_document(self, *, doc_id: str) -> None: ...

    def delete_by_folder_prefix(self, *, owner_id: str, folder_path: str) -> None: ...


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
        # overwrites the same document instead of creating a duplicate.
        self._client.index(index=self._alias, id=doc_id, document=document)

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
                        {
                            "bool": {
                                "should": [
                                    {"term": {"folder_path": folder_path}},
                                    {"prefix": {"folder_path": f"{folder_path}."}},
                                ],
                                "minimum_should_match": 1,
                            }
                        },
                    ]
                }
            },
            conflicts="proceed",
        )
