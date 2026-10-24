"""Entrada da Lambda. Handler: catalog_action.handler.lambda_handler.

Atende dois chamadores com a mesma lógica: o AgentCore Gateway (tool MCP) e o
Bedrock Agents (action group com OpenAPI). Só a tradução de entrada e saída muda.
"""

import functools
import logging
import os

from . import bedrock_io, gateway_io
from .catalog import Catalog, CatalogError, DynamoCatalog
from .payload import TRUNCATED_NOTE, fit_body
from .routes import ROUTES, TOOLS, BadRequest, search

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


@functools.cache
def _default_catalog() -> Catalog:
    # Criado uma vez por container: reaproveita a conexão entre invocações.
    return DynamoCatalog.from_env()


def handle(
    api_path: str, http_method: str, params: dict[str, str], catalog: Catalog | None
) -> tuple[int, dict]:
    """Lógica comum aos dois formatos. Devolve (status HTTP, corpo)."""
    # Só nomes de parâmetro: o valor é texto do usuário e pode carregar PII.
    logger.info("action request", extra={"api_path": api_path, "params": sorted(params)})

    route = ROUTES.get(api_path)
    if route is None:
        return 404, {"error": "unknown_path", "message": f"{api_path} not found"}
    if http_method != "GET":
        return 405, {"error": "method_not_allowed", "message": "only GET is supported"}

    try:
        body = search(route, catalog or _default_catalog(), params)
    except BadRequest as exc:
        return 400, {"error": "bad_request", "message": str(exc)}
    except CatalogError:
        logger.exception("catalog unavailable")
        return 503, {
            "error": "catalog_unavailable",
            "message": "The catalog could not be searched. Tell the user the search "
            "failed and do not answer from memory.",
        }

    if body["total_matches"] == 0:
        body["note"] = "No items matched. Suggest removing a filter."
    elif body["truncated"]:
        body["note"] = TRUNCATED_NOTE
    logger.info("action result", extra={"count": body["count"], "total": body["total_matches"]})
    return 200, body


def lambda_handler(event: dict, context: object, catalog: Catalog | None = None) -> dict:
    if tool := gateway_io.tool_name(context):
        api_path = TOOLS.get(tool)
        if api_path is None:
            return {"error": "unknown_tool", "message": f"{tool} is not a catalog tool"}
        _, body = handle(api_path, "GET", gateway_io.parse_params(event), catalog)
        return fit_body(body)

    request = bedrock_io.parse_event(event)
    status, body = handle(request.api_path, request.http_method, request.params, catalog)
    return bedrock_io.build_response(request, status, body)
