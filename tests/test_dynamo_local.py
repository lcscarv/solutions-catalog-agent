"""Integração com o DynamoDB Local. Rode `make up && make seed-local` antes."""

import os
import socket
from urllib.parse import urlparse

import pytest

from catalog_action.catalog import DynamoCatalog
from catalog_action.routes import ROUTES, search

ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT_URL", "http://localhost:8000")


def _reachable(url: str) -> bool:
    parsed = urlparse(url)
    try:
        with socket.create_connection((parsed.hostname, parsed.port or 80), timeout=0.5):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _reachable(ENDPOINT), reason="DynamoDB Local fora do ar"),
]


@pytest.fixture
def dynamo_catalog(monkeypatch):
    monkeypatch.setenv("DYNAMODB_ENDPOINT_URL", ENDPOINT)
    monkeypatch.setenv("CATALOG_TABLE", os.environ.get("CATALOG_TABLE", "solutions-catalog-local"))
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "local")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "local")
    return DynamoCatalog.from_env()


def test_query_returns_seeded_partition(dynamo_catalog, catalog_items):
    expected = {i["asset_id"] for i in catalog_items if i["asset_type"] == "case_study"}
    got = {i["asset_id"] for i in dynamo_catalog.list_assets("case_study")}
    assert got == expected


def test_search_end_to_end(dynamo_catalog):
    result = search(ROUTES["/case-studies"], dynamo_catalog, {"industry": "energy"})
    assert [i["id"] for i in result["items"]] == ["cs-006"]
