from unittest.mock import MagicMock

import pytest
from elastic_transport import ConnectionError as ESConnectionError

from app.es_index import ElasticsearchIndex, SearchIndexUnavailableError

# These tests deliberately never touch a real cluster -- decision 15 requires
# a 503 when Elasticsearch is unreachable, and the only reliable way to
# exercise "unreachable" without flakiness is to mock the transport error.


def test_search_raises_unavailable_when_elasticsearch_is_unreachable() -> None:
    client = MagicMock()
    client.search.side_effect = ESConnectionError("connection refused")
    index = ElasticsearchIndex(client)

    with pytest.raises(SearchIndexUnavailableError):
        index.search(
            owner_id="owner-1",
            folder_path="root",
            query=None,
            category=None,
            limit=10,
            search_after=None,
        )


def test_is_healthy_returns_false_when_elasticsearch_is_unreachable() -> None:
    client = MagicMock()
    client.ping.side_effect = ESConnectionError("connection refused")
    index = ElasticsearchIndex(client)

    assert index.is_healthy() is False


def test_is_healthy_returns_true_when_ping_succeeds() -> None:
    client = MagicMock()
    client.ping.return_value = True
    index = ElasticsearchIndex(client)

    assert index.is_healthy() is True
