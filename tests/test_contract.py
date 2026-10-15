"""O schema OpenAPI é o que o modelo lê. Ele não pode divergir do código nem dos dados."""

from pathlib import Path

import pytest
import yaml

from catalog_action.routes import ROUTES

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load((ROOT / "contracts" / "catalog_api.yaml").read_text())


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
