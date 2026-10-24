"""Tool search_documents: filtros de metadado, limites e falhas, sem chamar a AWS."""

import pytest
from botocore.exceptions import ClientError

from docs_search.handler import MAX_PASSAGE_CHARS, build_filter, lambda_handler

from .conftest import gateway_context


class FakeRuntime:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.calls = []

    def retrieve(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"retrievalResults": self.results}


def result(key: str, score: float, text: str = "texto", asset_id: str = "cs-001") -> dict:
    return {
        "content": {"text": text},
        "location": {"s3Location": {"uri": f"s3://bucket-docs/{key}"}},
        "metadata": {"asset_id": asset_id},
        "score": score,
    }


@pytest.fixture(autouse=True)
def kb_id(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_BASE_ID", "KB123")


def call(client, **args) -> dict:
    return lambda_handler(args, gateway_context("search_documents", target="docs"), client)


def vector_config(client) -> dict:
    return client.calls[-1]["retrievalConfiguration"]["vectorSearchConfiguration"]


def test_maps_results_to_source_score_and_text():
    client = FakeRuntime([result("case-studies/acme.md", 0.61234)])
    body = call(client, query="varejo")
    assert body["count"] == 1
    assert body["results"][0] == {
        "source": "case-studies/acme.md",
        "asset_id": "cs-001",
        "score": 0.612,
        "text": "texto",
    }
    assert client.calls[0]["knowledgeBaseId"] == "KB123"


def test_without_filters_sends_no_filter():
    client = FakeRuntime()
    call(client, query="x")
    assert "filter" not in vector_config(client)


def test_one_filter_is_a_plain_equals():
    assert build_filter("case_study", None) == {
        "equals": {"key": "asset_type", "value": "case_study"}
    }


def test_two_filters_are_combined_with_and_all():
    flt = build_filter("case_study", "Retail")
    assert [c["equals"]["key"] for c in flt["andAll"]] == ["asset_type", "industry"]


def test_filter_values_are_matched_case_insensitively():
    """O índice compara exato; o modelo pode mandar "retail"."""
    client = FakeRuntime()
    call(client, query="x", industry="retail")
    assert vector_config(client)["filter"]["equals"]["value"] == "Retail"


def test_unknown_filter_value_lists_the_allowed_ones():
    body = call(FakeRuntime(), query="x", asset_type="slides")
    assert body["error"] == "bad_request"
    assert "case_study" in body["message"]


def test_query_is_required():
    assert call(FakeRuntime(), query="  ")["error"] == "bad_request"


def test_limit_default_and_bounds():
    client = FakeRuntime()
    call(client, query="x")
    assert vector_config(client)["numberOfResults"] == 5
    assert call(client, query="x", limit=50)["error"] == "bad_request"


def test_long_passage_is_cut():
    body = call(FakeRuntime([result("a.md", 0.5, text="y" * 5000)]), query="x")
    assert len(body["results"][0]["text"]) == MAX_PASSAGE_CHARS


def test_no_result_adds_note():
    body = call(FakeRuntime(), query="x", asset_type="case_study")
    assert body["results"] == []
    assert "note" in body


def test_kb_failure_is_an_error_never_an_empty_result():
    error = ClientError({"Error": {"Code": "ThrottlingException", "Message": "slow"}}, "Retrieve")
    body = call(FakeRuntime(error=error), query="x")
    assert body["error"] == "search_unavailable"


def test_other_tool_name_is_rejected():
    body = lambda_handler({"query": "x"}, gateway_context("search_cases", "docs"), FakeRuntime())
    assert body["error"] == "unknown_tool"


def test_query_text_is_not_logged(caplog):
    caplog.set_level("INFO")
    call(FakeRuntime(), query="secret-client-name")
    assert "secret-client-name" not in caplog.text
