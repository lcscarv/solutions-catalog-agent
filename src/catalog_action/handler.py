"""Entrada da Lambda. Handler: catalog_action.handler.lambda_handler."""

import logging
import os

from .bedrock_io import build_response, parse_event
from .catalog import Catalog, CatalogError, DynamoCatalog
from .routes import ROUTES, BadRequest, search

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_catalog: Catalog | None = None


def _default_catalog() -> Catalog:
    # Criado uma vez por container: reaproveita a conexão entre invocações.
    global _catalog
    if _catalog is None:
        _catalog = DynamoCatalog.from_env()
    return _catalog


def lambda_handler(event: dict, context: object, catalog: Catalog | None = None) -> dict:
    request = parse_event(event)
    # Só nomes de parâmetro: o valor é texto do usuário e pode carregar PII.
    logger.info(
        "action request",
        extra={"api_path": request.api_path, "params": sorted(request.params)},
    )

    route = ROUTES.get(request.api_path)
    if route is None:
        return build_response(
            request, 404, {"error": "unknown_path", "message": f"{request.api_path} not found"}
        )
    if request.http_method != "GET":
        return build_response(
            request, 405, {"error": "method_not_allowed", "message": "only GET is supported"}
        )

    try:
        body = search(route, catalog or _default_catalog(), request.params)
    except BadRequest as exc:
        return build_response(request, 400, {"error": "bad_request", "message": str(exc)})
    except CatalogError:
        logger.exception("catalog unavailable")
        return build_response(
            request,
            503,
            {
                "error": "catalog_unavailable",
                "message": "The catalog could not be searched. Tell the user the search "
                "failed and do not answer from memory.",
            },
        )

    if body["total_matches"] == 0:
        body["note"] = "No items matched. Suggest removing a filter."
    logger.info("action result", extra={"count": body["count"], "total": body["total_matches"]})
    return build_response(request, 200, body)
