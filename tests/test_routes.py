import pytest

from catalog_action.routes import MAX_LIMIT, ROUTES, BadRequest, parse_limit, search


def ids(result: dict) -> set[str]:
    return {item["id"] for item in result["items"]}


def test_filters_combine_with_and(catalog):
    result = search(
        ROUTES["/case-studies"], catalog, {"industry": "retail", "solution": "generative"}
    )
    assert ids(result) == {"cs-001"}


def test_no_filter_returns_whole_type(catalog, catalog_items):
    expected = sum(1 for i in catalog_items if i["asset_type"] == "case_study")
    assert search(ROUTES["/case-studies"], catalog, {})["total_matches"] == expected


def test_blank_filter_is_ignored(catalog):
    with_blank = search(ROUTES["/case-studies"], catalog, {"industry": "  "})
    without = search(ROUTES["/case-studies"], catalog, {})
    assert with_blank == without


def test_tag_matches_inside_list(catalog):
    result = search(ROUTES["/strategic-materials"], catalog, {"tag": "first-call"})
    assert ids(result) == {"sm-002", "sm-004"}


def test_query_searches_title_and_description(catalog):
    result = search(ROUTES["/support-materials"], catalog, {"query": "roi"})
    assert ids(result) == {"sp-001"}


def test_limit_truncates_and_reports(catalog):
    result = search(ROUTES["/case-studies"], catalog, {"limit": "2"})
    assert result["count"] == 2
    assert result["truncated"] is True
    assert result["total_matches"] > 2


def test_description_is_not_returned(catalog):
    result = search(ROUTES["/support-materials"], catalog, {})
    assert all("description" not in item for item in result["items"])


@pytest.mark.parametrize("raw", ["0", str(MAX_LIMIT + 1), "ten", "-1"])
def test_invalid_limit_is_rejected(raw):
    with pytest.raises(BadRequest):
        parse_limit(raw)


def test_missing_limit_uses_default():
    assert parse_limit(None) == 10
