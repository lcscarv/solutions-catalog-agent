"""Entrada da Lambda. Handler: docs_search.handler.lambda_handler.

Tool `search_documents` do Gateway: busca semântica no texto dos documentos.
O que é categoria (tipo de documento, indústria) vai como filtro de metadado,
não para o embedding: todos os documentos falam de temas parecidos, e sem
filtro um deck genérico ganha de um case específico.
"""

import functools
import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

TOOL_NAME = "search_documents"
DELIMITER = "___"

# Valores dos metadados na ingestão (data/docs/**/*.metadata.json).
ASSET_TYPES = ("case_study", "strategic_material", "support_material")
INDUSTRIES = ("Retail", "Financial Services", "Healthcare", "Manufacturing", "Energy")

DEFAULT_LIMIT = 5
MAX_LIMIT = 10
# Um trecho por resultado basta para o modelo responder; o resto é token.
MAX_PASSAGE_CHARS = 1500


class BadRequest(Exception):
    """Parâmetro inválido. A mensagem diz ao modelo como corrigir a chamada."""


@functools.cache
def _bedrock_runtime():
    # Criado uma vez por container. Não no import: sem região, os testes quebrariam.
    return boto3.client("bedrock-agent-runtime")


def _canonical(value: str, allowed: tuple[str, ...], name: str) -> str:
    """O modelo pode mandar "retail"; o filtro do índice compara exato."""
    by_lower = {a.lower(): a for a in allowed}
    try:
        return by_lower[value.strip().lower()]
    except KeyError as exc:
        raise BadRequest(f"{name} must be one of: {', '.join(allowed)}") from exc


def _limit(raw: object) -> int:
    if raw in (None, ""):
        return DEFAULT_LIMIT
    try:
        value = int(str(raw).strip())
    except ValueError as exc:
        raise BadRequest(f"limit must be an integer between 1 and {MAX_LIMIT}") from exc
    if not 1 <= value <= MAX_LIMIT:
        raise BadRequest(f"limit must be between 1 and {MAX_LIMIT}")
    return value


def build_filter(asset_type: str | None, industry: str | None) -> dict | None:
    conditions = []
    if asset_type and asset_type.strip():
        value = _canonical(asset_type, ASSET_TYPES, "asset_type")
        conditions.append({"equals": {"key": "asset_type", "value": value}})
    if industry and industry.strip():
        value = _canonical(industry, INDUSTRIES, "industry")
        conditions.append({"equals": {"key": "industry", "value": value}})
    if not conditions:
        return None
    # andAll exige pelo menos duas condições.
    return conditions[0] if len(conditions) == 1 else {"andAll": conditions}


def search(event: dict, client, knowledge_base_id: str) -> dict:
    query = str(event.get("query") or "").strip()
    if not query:
        raise BadRequest("query is required")
    vector_config: dict = {"numberOfResults": _limit(event.get("limit"))}
    flt = build_filter(event.get("asset_type"), event.get("industry"))
    if flt is not None:
        vector_config["filter"] = flt

    results = client.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": vector_config},
    )["retrievalResults"]

    passages = [
        {
            "source": r["location"]["s3Location"]["uri"].split("/", 3)[-1],
            "asset_id": (r.get("metadata") or {}).get("asset_id"),
            "score": round(r.get("score", 0.0), 3),
            "text": r["content"]["text"][:MAX_PASSAGE_CHARS],
        }
        for r in results
    ]
    body: dict = {"results": passages, "count": len(passages)}
    if not passages:
        body["note"] = "No passages matched. Try again without asset_type or industry."
    return body


def lambda_handler(event: dict, context: object, client=None) -> dict:
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    tool = custom.get("bedrockAgentCoreToolName", "").split(DELIMITER, 1)[-1]
    # Só nomes de parâmetro: a pergunta é texto do usuário e pode carregar PII.
    logger.info("tool request", extra={"tool": tool, "params": sorted(event or {})})
    if tool != TOOL_NAME:
        return {"error": "unknown_tool", "message": f"{tool} is not a document tool"}

    try:
        body = search(event or {}, client or _bedrock_runtime(), os.environ["KNOWLEDGE_BASE_ID"])
    except BadRequest as exc:
        return {"error": "bad_request", "message": str(exc)}
    except (ClientError, BotoCoreError):
        logger.exception("knowledge base unavailable")
        return {
            "error": "search_unavailable",
            "message": "The document search failed. Tell the user the search failed "
            "and do not answer from memory.",
        }
    logger.info("tool result", extra={"count": body["count"]})
    return body
