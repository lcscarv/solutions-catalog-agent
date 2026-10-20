"""Mapa apiPath -> tipo de ativo e filtros. Espelha contracts/catalog_api.yaml
(Bedrock Agents) e contracts/catalog_tools.json (AgentCore Gateway).

O teste de contrato (tests/test_contract.py) falha se este arquivo e os
contratos divergirem, para o schema que o modelo lê nunca mentir sobre o que o
código faz.
"""

from dataclasses import dataclass

from .catalog import Catalog
from .matching import field_contains, normalize

DEFAULT_LIMIT = 10
MAX_LIMIT = 25

# Campos devolvidos ao agente. Descrição longa fica de fora: só infla tokens.
PROJECTED_FIELDS = ("asset_id", "title", "client", "industry", "solution", "tags", "link")


class BadRequest(Exception):
    """Parâmetro inválido. Vira 400 com a mensagem para o modelo corrigir a chamada."""


@dataclass(frozen=True)
class Route:
    asset_type: str
    # parâmetro da API -> campos do item onde ele é procurado
    filters: dict[str, tuple[str, ...]]


ROUTES: dict[str, Route] = {
    "/case-studies": Route(
        "case_study",
        {"industry": ("industry",), "solution": ("solution",)},
    ),
    "/strategic-materials": Route(
        "strategic_material",
        {"solution": ("solution",), "tag": ("tags",)},
    ),
    "/support-materials": Route(
        "support_material",
        {"solution": ("solution",), "query": ("title", "description")},
    ),
}

# Nome da tool no Gateway -> apiPath. O nome é o operationId do OpenAPI.
TOOLS: dict[str, str] = {
    "search_case_studies": "/case-studies",
    "search_strategic_materials": "/strategic-materials",
    "search_support_materials": "/support-materials",
}


def parse_limit(raw: str | None) -> int:
    if raw is None or str(raw).strip() == "":
        return DEFAULT_LIMIT
    try:
        value = int(str(raw).strip())
    except ValueError as exc:
        raise BadRequest(f"limit must be an integer between 1 and {MAX_LIMIT}") from exc
    if not 1 <= value <= MAX_LIMIT:
        raise BadRequest(f"limit must be between 1 and {MAX_LIMIT}")
    return value


def project(item: dict) -> dict:
    out = {k: item[k] for k in PROJECTED_FIELDS if item.get(k) not in (None, "", [])}
    if "asset_id" in out:
        out["id"] = out.pop("asset_id")
    return out


def search(route: Route, catalog: Catalog, params: dict[str, str]) -> dict:
    limit = parse_limit(params.get("limit"))
    needles = {
        name: normalize(value)
        for name in route.filters
        if (value := params.get(name)) and value.strip()
    }

    def matches(item: dict) -> bool:
        return all(
            any(field_contains(item.get(field), needle) for field in route.filters[name])
            for name, needle in needles.items()
        )

    matched = sorted(
        (i for i in catalog.list_assets(route.asset_type) if matches(i)),
        key=lambda i: str(i.get("title", "")),
    )
    page = matched[:limit]
    return {
        "items": [project(i) for i in page],
        "count": len(page),
        "total_matches": len(matched),
        "truncated": len(matched) > len(page),
    }
