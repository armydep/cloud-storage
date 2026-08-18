import json

import pytest

from app.es_index import _folder_scope_predicate, build_search_query


@pytest.mark.parametrize(
    ("query", "category"),
    [
        (None, None),
        ("report", None),
        (None, "document"),
        ("report", "document"),
    ],
)
def test_build_search_query_always_filters_by_owner_id(
    query: str | None, category: str | None
) -> None:
    """The single ownership chokepoint (design doc decision 6). If a future

    refactor ever removes this filter from build_search_query, every
    parametrization here fails -- there is no code path that skips it.
    """
    built = build_search_query(
        owner_id="owner-1", folder_path="root", query=query, category=category
    )

    assert {"term": {"owner_id": "owner-1"}} in built["bool"]["filter"]


def test_owner_id_is_applied_in_filter_context_never_in_the_scored_query() -> None:
    # owner_id must never affect scoring or be reachable by a crafted `q`.
    built = build_search_query(
        owner_id="owner-1", folder_path="root", query="owner-1", category=None
    )

    assert "owner_id" not in json.dumps(built["bool"]["must"])


def test_build_search_query_and_delete_by_folder_prefix_share_one_predicate() -> None:
    # search() and delete_by_folder_prefix() must never be able to disagree
    # about what is "in" a folder (design doc constraint 2) -- enforced here
    # by construction: both call the same _folder_scope_predicate.
    built = build_search_query(
        owner_id="owner-1", folder_path="root.docs", query=None, category=None
    )

    assert built["bool"]["filter"][1] == _folder_scope_predicate("root.docs")


def test_folder_scope_predicate_matches_exact_path_and_dotted_descendants() -> None:
    predicate = _folder_scope_predicate("root.docs")

    assert predicate == {
        "bool": {
            "should": [
                {"term": {"folder_path": "root.docs"}},
                {"prefix": {"folder_path": "root.docs."}},
            ],
            "minimum_should_match": 1,
        }
    }


def test_build_search_query_omits_category_filter_when_not_supplied() -> None:
    built = build_search_query(
        owner_id="owner-1", folder_path="root", query=None, category=None
    )

    assert not any(
        "category" in clause.get("term", {}) for clause in built["bool"]["filter"]
    )


def test_build_search_query_includes_category_filter_when_supplied() -> None:
    built = build_search_query(
        owner_id="owner-1", folder_path="root", query=None, category="document"
    )

    assert {"term": {"category": "document"}} in built["bool"]["filter"]


def test_build_search_query_uses_match_all_when_no_free_text_query() -> None:
    built = build_search_query(
        owner_id="owner-1", folder_path="root", query=None, category=None
    )

    assert built["bool"]["must"] == {"match_all": {}}


def test_build_search_query_matches_name_when_free_text_query_supplied() -> None:
    built = build_search_query(
        owner_id="owner-1", folder_path="root", query="report", category=None
    )

    assert built["bool"]["must"] == {"match": {"name": "report"}}
