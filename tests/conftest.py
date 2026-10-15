import json
from pathlib import Path

import pytest

from catalog_action.catalog import InMemoryCatalog

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def catalog_items() -> list[dict]:
    return json.loads((ROOT / "data" / "catalog.json").read_text())


@pytest.fixture
def catalog(catalog_items) -> InMemoryCatalog:
    return InMemoryCatalog(catalog_items)


def bedrock_event(api_path: str, method: str = "GET", **params) -> dict:
    """Evento no formato que o Bedrock Agents envia para a Lambda."""
    return {
        "messageVersion": "1.0",
        "actionGroup": "catalog",
        "apiPath": api_path,
        "httpMethod": method,
        "parameters": [{"name": k, "type": "string", "value": str(v)} for k, v in params.items()],
        "sessionAttributes": {"user_group": "sales"},
        "promptSessionAttributes": {},
    }
