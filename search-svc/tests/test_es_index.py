import uuid
from collections.abc import Generator

import pytest
from elasticsearch import Elasticsearch
from testcontainers.community.elasticsearch import ElasticSearchContainer

from app.es_index import ElasticsearchIndex

ES_IMAGE = "elasticsearch:8.17.0"


@pytest.fixture(scope="module")
def es_client() -> Generator[Elasticsearch, None, None]:
    container = ElasticSearchContainer(ES_IMAGE, mem_limit="1G")
    container.with_env("discovery.type", "single-node")
    container.with_env("ES_JAVA_OPTS", "-Xms512m -Xmx512m")
    # Test hosts can be disk-constrained in ways production never is; this
    # decider has nothing to do with what this suite verifies (mapping,
    # analyzer, alias, idempotent deletes), so disable it here only.
    container.with_env("cluster.routing.allocation.disk.threshold_enabled", "false")
    with container as started:
        client = Elasticsearch(
            f"http://{started.get_container_host_ip()}:"
            f"{started.get_exposed_port(started.port)}",
            request_timeout=30,
        )
        client.cluster.health(wait_for_status="yellow", timeout="60s")
        yield client


@pytest.fixture
def index(es_client: Elasticsearch) -> Generator[ElasticsearchIndex, None, None]:
    unique = uuid.uuid4().hex
    index_name = f"files-test-{unique}"
    alias = f"files-alias-{unique}"
    search_index = ElasticsearchIndex(es_client, alias=alias, index_name=index_name)
    search_index.ensure_index()
    yield search_index
    es_client.indices.delete(index=index_name, ignore_unavailable=True)


def _document(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "owner_id": "owner-1",
        "name": "report.pdf",
        "folder_path": "root.reports",
        "mime_type": "application/pdf",
        "category": "document",
        "size_bytes": 123,
        "created_at": "2026-08-17T00:00:00+00:00",
    }
    document.update(overrides)
    return document


def test_ensure_index_creates_index_reachable_through_its_alias(
    es_client: Elasticsearch, index: ElasticsearchIndex
) -> None:
    assert es_client.indices.exists(index=index._index_name)
    assert es_client.indices.exists_alias(name=index._alias)


def test_ensure_index_is_idempotent(index: ElasticsearchIndex) -> None:
    index.ensure_index()
    index.ensure_index()


def test_index_and_delete_document_round_trip(
    es_client: Elasticsearch, index: ElasticsearchIndex
) -> None:
    index.index_document(doc_id="file-1", document=_document())
    es_client.indices.refresh(index=index._alias)
    assert es_client.get(index=index._alias, id="file-1")["found"] is True

    index.delete_document(doc_id="file-1")
    es_client.indices.refresh(index=index._alias)
    assert not es_client.exists(index=index._alias, id="file-1")


def test_delete_document_when_missing_is_a_noop(index: ElasticsearchIndex) -> None:
    index.delete_document(doc_id="never-indexed")


def test_delete_by_folder_prefix_removes_only_matching_documents(
    es_client: Elasticsearch, index: ElasticsearchIndex
) -> None:
    index.index_document(
        doc_id="in-folder", document=_document(folder_path="root.reports")
    )
    index.index_document(
        doc_id="in-subfolder",
        document=_document(folder_path="root.reports.q1"),
    )
    index.index_document(
        doc_id="sibling-folder",
        document=_document(folder_path="root.reports_2024"),
    )
    index.index_document(
        doc_id="other-owner",
        document=_document(owner_id="owner-2", folder_path="root.reports"),
    )
    es_client.indices.refresh(index=index._alias)

    index.delete_by_folder_prefix(owner_id="owner-1", folder_path="root.reports")
    es_client.indices.refresh(index=index._alias)

    assert not es_client.exists(index=index._alias, id="in-folder")
    assert not es_client.exists(index=index._alias, id="in-subfolder")
    assert es_client.exists(index=index._alias, id="sibling-folder")
    assert es_client.exists(index=index._alias, id="other-owner")


def test_filename_analyzer_splits_on_separators(
    es_client: Elasticsearch, index: ElasticsearchIndex
) -> None:
    index.index_document(
        doc_id="file-1", document=_document(name="report_2024-final.pdf")
    )
    es_client.indices.refresh(index=index._alias)

    for term in ("report", "2024", "final"):
        response = es_client.search(index=index._alias, query={"match": {"name": term}})
        assert response["hits"]["total"]["value"] == 1, term


def test_search_never_returns_another_owners_files(
    es_client: Elasticsearch, index: ElasticsearchIndex
) -> None:
    """The primary acceptance criterion for #134: a search endpoint returns a

    list, so one missing owner filter leaks many records at once. Two owners,
    identical filenames, same folder -- the only thing that can separate them
    is owner_id.
    """
    index.index_document(
        doc_id="mine", document=_document(owner_id="owner-1", name="shared_name.pdf")
    )
    index.index_document(
        doc_id="theirs",
        document=_document(owner_id="owner-2", name="shared_name.pdf"),
    )
    es_client.indices.refresh(index=index._alias)

    hits = index.search(
        owner_id="owner-1",
        folder_path="root.reports",
        query=None,
        category=None,
        limit=10,
        search_after=None,
    )

    assert {hit.doc_id for hit in hits} == {"mine"}


def test_search_with_another_owners_folder_path_returns_nothing(
    es_client: Elasticsearch, index: ElasticsearchIndex
) -> None:
    # owner_id filters independently of folder_path -- passing someone else's
    # real folder path must not leak their files.
    index.index_document(
        doc_id="mine",
        document=_document(owner_id="owner-1", folder_path="root.docs"),
    )
    es_client.indices.refresh(index=index._alias)

    hits = index.search(
        owner_id="owner-2",
        folder_path="root.docs",
        query=None,
        category=None,
        limit=10,
        search_after=None,
    )

    assert hits == []


def test_search_includes_nested_subfolders_but_not_sibling_folders(
    es_client: Elasticsearch, index: ElasticsearchIndex
) -> None:
    index.index_document(doc_id="direct", document=_document(folder_path="root.docs"))
    index.index_document(
        doc_id="nested", document=_document(folder_path="root.docs.2026.q1")
    )
    index.index_document(
        doc_id="sibling", document=_document(folder_path="root.docsarchive")
    )
    es_client.indices.refresh(index=index._alias)

    hits = index.search(
        owner_id="owner-1",
        folder_path="root.docs",
        query=None,
        category=None,
        limit=10,
        search_after=None,
    )

    assert {hit.doc_id for hit in hits} == {"direct", "nested"}


def test_search_filters_by_category(
    es_client: Elasticsearch, index: ElasticsearchIndex
) -> None:
    index.index_document(doc_id="doc", document=_document(category="document"))
    index.index_document(doc_id="img", document=_document(category="image"))
    es_client.indices.refresh(index=index._alias)

    hits = index.search(
        owner_id="owner-1",
        folder_path="root.reports",
        query=None,
        category="image",
        limit=10,
        search_after=None,
    )

    assert {hit.doc_id for hit in hits} == {"img"}


def test_search_matches_name_using_the_filename_analyzer(
    es_client: Elasticsearch, index: ElasticsearchIndex
) -> None:
    index.index_document(
        doc_id="file-1", document=_document(name="report_2024-final.pdf")
    )
    index.index_document(doc_id="file-2", document=_document(name="unrelated.pdf"))
    es_client.indices.refresh(index=index._alias)

    hits = index.search(
        owner_id="owner-1",
        folder_path="root.reports",
        query="2024",
        category=None,
        limit=10,
        search_after=None,
    )

    assert {hit.doc_id for hit in hits} == {"file-1"}


def test_search_pagination_does_not_duplicate_or_skip_tied_results(
    es_client: Elasticsearch, index: ElasticsearchIndex
) -> None:
    # Identical created_at forces the _id tiebreaker (decision 16) to do all
    # the ordering work -- without it, search_after would duplicate or skip.
    for i in range(5):
        index.index_document(
            doc_id=f"file-{i}",
            document=_document(
                name=f"file-{i}.pdf", created_at="2026-08-17T00:00:00+00:00"
            ),
        )
    es_client.indices.refresh(index=index._alias)

    seen: list[str] = []
    search_after: list[object] | None = None
    for _ in range(10):  # far more than enough pages for 5 documents at size 2
        hits = index.search(
            owner_id="owner-1",
            folder_path="root.reports",
            query=None,
            category=None,
            limit=2,
            search_after=search_after,
        )
        if not hits:
            break
        seen.extend(hit.doc_id for hit in hits)
        search_after = hits[-1].sort

    assert seen == sorted(f"file-{i}" for i in range(5))
    assert len(seen) == len(set(seen))


def test_search_returns_empty_when_the_index_does_not_exist_yet(
    es_client: Elasticsearch,
) -> None:
    # A fresh deployment where the indexer hasn't created the alias yet is a
    # genuinely empty result, not an outage (see the mirrored NotFoundError
    # handling in ElasticsearchIndex.search).
    never_created = ElasticsearchIndex(
        es_client, alias="files-never-created", index_name="files-never-created-v1"
    )

    hits = never_created.search(
        owner_id="owner-1",
        folder_path="root",
        query=None,
        category=None,
        limit=10,
        search_after=None,
    )

    assert hits == []
