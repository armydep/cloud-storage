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
