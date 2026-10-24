"""A Lambda do catálogo chamada pelo AgentCore Gateway: mesma lógica, outro formato."""

import json

from catalog_action import payload
from catalog_action.catalog import CatalogError, InMemoryCatalog
from catalog_action.handler import lambda_handler

from .conftest import gateway_context


def call(tool: str, catalog, **args) -> dict:
    return lambda_handler(args, gateway_context(tool), catalog)


def test_tool_name_routes_to_the_same_search(catalog):
    body = call("search_case_studies", catalog, industry="Retail")
    assert body["count"] >= 1
    assert all(item["industry"] == "Retail" for item in body["items"])


def test_response_is_plain_json_without_bedrock_envelope(catalog):
    body = call("search_strategic_materials", catalog)
    assert "messageVersion" not in body
    assert set(body) >= {"items", "count", "total_matches", "truncated"}


def test_numeric_limit_from_the_model_is_accepted(catalog):
    body = call("search_case_studies", catalog, limit=1)
    assert body["count"] == 1


def test_null_argument_is_ignored(catalog):
    body = call("search_case_studies", catalog, industry=None)
    assert body["total_matches"] == call("search_case_studies", catalog)["total_matches"]


def test_unknown_tool_is_an_error_not_an_empty_list(catalog):
    body = call("delete_everything", catalog)
    assert body["error"] == "unknown_tool"


def test_bad_limit_comes_back_as_message_for_the_model(catalog):
    body = call("search_case_studies", catalog, limit="abc")
    assert body["error"] == "bad_request"
    assert "limit" in body["message"]


class BrokenCatalog:
    def list_assets(self, asset_type):
        raise CatalogError("connection refused")


def test_catalog_failure_is_an_error_never_an_empty_result():
    body = call("search_case_studies", BrokenCatalog())
    assert body["error"] == "catalog_unavailable"


def test_partial_page_tells_the_model_to_offer_a_filter(catalog):
    """Resultado grande não é erro: vem a primeira página e uma instrução."""
    body = call("search_case_studies", catalog, limit=1)
    assert body["truncated"] is True
    assert body["total_matches"] > body["count"] == 1
    assert body["note"] == payload.TRUNCATED_NOTE


def test_full_page_has_no_truncation_note(catalog):
    body = call("search_case_studies", catalog, industry="Retail")
    assert body["truncated"] is False
    assert "note" not in body


def test_large_result_is_cut_to_fit_and_logged(monkeypatch, caplog):
    monkeypatch.setattr(payload, "MAX_BODY_BYTES", 600)
    items = [
        {"asset_type": "case_study", "asset_id": f"cs-{n:03}", "title": "x" * 80} for n in range(20)
    ]
    body = call("search_case_studies", InMemoryCatalog(items), limit=20)
    assert len(json.dumps(body).encode()) <= 600
    assert body["truncated"] is True
    assert body["note"] == payload.TRUNCATED_NOTE
    # Rede de segurança: se disparar, a projeção ou o limit estão errados.
    assert "response cut to fit" in caplog.text


def test_without_gateway_context_falls_back_to_bedrock_format(catalog):
    from .conftest import bedrock_event

    response = lambda_handler(bedrock_event("/case-studies"), None, catalog)
    assert response["messageVersion"] == "1.0"
