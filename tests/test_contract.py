"""Os contratos são o que o modelo lê. Eles não podem divergir do código nem dos dados.

Dois contratos para a mesma Lambda do catálogo: o OpenAPI (Bedrock Agents) e as
tool definitions do AgentCore Gateway. O schema do Gateway não tem `enum`, então
os valores permitidos vão na descrição, e estes testes garantem que estão lá.
"""

import json
from pathlib import Path

import pytest
import yaml

from catalog_action.routes import ROUTES, TOOLS
from docs_search.handler import ASSET_TYPES, INDUSTRIES

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load((ROOT / "contracts" / "catalog_api.yaml").read_text())
CATALOG_TOOLS = {
    t["name"]: t for t in json.loads((ROOT / "contracts" / "catalog_tools.json").read_text())
}
DOCS_TOOLS = {
    t["name"]: t for t in json.loads((ROOT / "contracts" / "docs_tools.json").read_text())
}

# Campos que o tool_schema do Gateway aceita (bloco property no Terraform).
GATEWAY_PROPERTY_FIELDS = {"type", "description"}


def spec_params(path: str) -> dict[str, dict]:
    return {p["name"]: p for p in SPEC["paths"][path]["get"]["parameters"]}


def test_every_route_is_in_the_spec_and_vice_versa():
    assert set(SPEC["paths"]) == set(ROUTES)


@pytest.mark.parametrize("path", sorted(ROUTES))
def test_spec_params_match_route_filters(path):
    assert set(spec_params(path)) == set(ROUTES[path].filters) | {"limit"}


@pytest.mark.parametrize("path", sorted(ROUTES))
def test_only_get_operations(path):
    assert set(SPEC["paths"][path]) == {"get"}


@pytest.mark.parametrize("path", sorted(ROUTES))
def test_every_operation_has_description_and_operation_id(path):
    op = SPEC["paths"][path]["get"]
    assert op.get("operationId")
    assert op.get("description")


@pytest.mark.parametrize("path", sorted(ROUTES))
def test_catalog_values_are_inside_enums(path, catalog_items):
    """Se o catálogo ganhar uma indústria nova, o enum precisa ganhar também."""
    route = ROUTES[path]
    for name, param in spec_params(path).items():
        enum = param["schema"].get("enum")
        if not enum:
            continue
        (field,) = route.filters[name]
        values = {i[field] for i in catalog_items if i["asset_type"] == route.asset_type}
        values.discard(None)
        assert values <= set(enum), f"{path}.{name}: {values - set(enum)} fora do enum"


# --- AgentCore Gateway ---------------------------------------------------------


def operation_ids() -> dict[str, str]:
    return {SPEC["paths"][p]["get"]["operationId"]: p for p in SPEC["paths"]}


def test_catalog_tools_are_the_openapi_operations():
    assert operation_ids() == TOOLS
    assert set(CATALOG_TOOLS) == set(TOOLS)


@pytest.mark.parametrize("tool", sorted(TOOLS))
def test_tool_properties_match_route_filters(tool):
    props = CATALOG_TOOLS[tool]["inputSchema"]["properties"]
    assert set(props) == set(ROUTES[TOOLS[tool]].filters) | {"limit"}


@pytest.mark.parametrize("tool", sorted(TOOLS))
def test_openapi_enums_are_spelled_out_in_tool_descriptions(tool):
    """Sem enum no Gateway, a descrição é o único lugar onde o modelo vê os valores."""
    props = CATALOG_TOOLS[tool]["inputSchema"]["properties"]
    for name, param in spec_params(TOOLS[tool]).items():
        for value in param["schema"].get("enum", []):
            assert value in props[name]["description"], f"{tool}.{name}: falta {value}"


@pytest.mark.parametrize("tool", sorted({**CATALOG_TOOLS, **DOCS_TOOLS}))
def test_tools_only_use_fields_the_gateway_schema_supports(tool):
    spec = {**CATALOG_TOOLS, **DOCS_TOOLS}[tool]
    assert spec["description"]
    schema = spec["inputSchema"]
    assert schema["type"] == "object"
    assert set(schema) <= {"type", "properties", "required"}
    for name, prop in schema["properties"].items():
        assert set(prop) <= GATEWAY_PROPERTY_FIELDS, f"{tool}.{name}"
        assert prop["type"] in {"string", "integer"}
        assert prop.get("description")
    assert set(schema.get("required", [])) <= set(schema["properties"])


def test_docs_tool_lists_every_filter_value():
    props = DOCS_TOOLS["search_documents"]["inputSchema"]["properties"]
    assert all(v in props["asset_type"]["description"] for v in ASSET_TYPES)
    assert all(v in props["industry"]["description"] for v in INDUSTRIES)


def test_indexed_metadata_fits_the_docs_filters():
    """Um metadado fora da lista nunca casaria com o filtro exato do índice."""
    for path in (ROOT / "data" / "docs").rglob("*.metadata.json"):
        attrs = json.loads(path.read_text())["metadataAttributes"]
        assert attrs["asset_type"] in ASSET_TYPES, path.name
        if "industry" in attrs:
            assert attrs["industry"] in INDUSTRIES, path.name
