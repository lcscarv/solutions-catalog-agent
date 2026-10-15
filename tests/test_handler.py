import json

from catalog_action import bedrock_io
from catalog_action.catalog import CatalogError, InMemoryCatalog
from catalog_action.handler import lambda_handler

from .conftest import bedrock_event


def body_of(response: dict) -> dict:
    return json.loads(response["response"]["responseBody"]["application/json"]["body"])


def status_of(response: dict) -> int:
    return response["response"]["httpStatusCode"]


def test_envelope_matches_bedrock_contract(catalog):
    response = lambda_handler(bedrock_event("/case-studies", industry="Retail"), None, catalog)
    assert response["messageVersion"] == "1.0"
    inner = response["response"]
    assert inner["actionGroup"] == "catalog"
    assert inner["apiPath"] == "/case-studies"
    assert inner["httpMethod"] == "GET"
    assert status_of(response) == 200
    assert response["sessionAttributes"] == {"user_group": "sales"}


def test_unknown_path_is_404_not_empty_list(catalog):
    assert status_of(lambda_handler(bedrock_event("/nope"), None, catalog)) == 404


def test_non_get_is_405(catalog):
    assert status_of(lambda_handler(bedrock_event("/case-studies", "POST"), None, catalog)) == 405


def test_bad_limit_is_400_with_message(catalog):
    response = lambda_handler(bedrock_event("/case-studies", limit="abc"), None, catalog)
    assert status_of(response) == 400
    assert "limit" in body_of(response)["message"]


class BrokenCatalog:
    def list_assets(self, asset_type):
        raise CatalogError("connection refused")


def test_catalog_failure_is_503_never_empty_200():
    response = lambda_handler(bedrock_event("/case-studies"), None, BrokenCatalog())
    assert status_of(response) == 503
    assert body_of(response)["error"] == "catalog_unavailable"


def test_no_match_adds_note(catalog):
    response = lambda_handler(bedrock_event("/case-studies", industry="Mining"), None, catalog)
    body = body_of(response)
    assert body["items"] == []
    assert "note" in body


def test_large_result_is_cut_to_fit(monkeypatch):
    monkeypatch.setattr(bedrock_io, "MAX_BODY_BYTES", 600)
    items = [
        {"asset_type": "case_study", "asset_id": f"cs-{n:03}", "title": "x" * 80} for n in range(20)
    ]
    response = lambda_handler(
        bedrock_event("/case-studies", limit="20"), None, InMemoryCatalog(items)
    )
    body = body_of(response)
    assert len(json.dumps(body).encode()) <= 600
    assert body["truncated"] is True
    assert body["count"] == len(body["items"]) < 20


def test_param_values_are_not_logged(catalog, caplog):
    caplog.set_level("INFO")
    lambda_handler(bedrock_event("/support-materials", query="secret-client-name"), None, catalog)
    assert "secret-client-name" not in caplog.text
