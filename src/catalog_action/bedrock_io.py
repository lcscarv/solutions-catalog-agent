"""Formato de entrada e saída do Bedrock Agents para Action Groups com OpenAPI."""

import json
from dataclasses import dataclass, field

# O Bedrock rejeita respostas de action group acima de cerca de 25 KB.
# Cortamos itens antes disso e avisamos o modelo com truncated=true.
MAX_BODY_BYTES = 20_000


@dataclass(frozen=True)
class ActionRequest:
    action_group: str
    api_path: str
    http_method: str
    params: dict[str, str]
    session_attributes: dict = field(default_factory=dict)
    prompt_session_attributes: dict = field(default_factory=dict)


def parse_event(event: dict) -> ActionRequest:
    params = {
        p["name"]: str(p.get("value", "")) for p in event.get("parameters") or [] if "name" in p
    }
    return ActionRequest(
        action_group=event.get("actionGroup", ""),
        api_path=event.get("apiPath", ""),
        http_method=(event.get("httpMethod") or "").upper(),
        params=params,
        session_attributes=event.get("sessionAttributes") or {},
        prompt_session_attributes=event.get("promptSessionAttributes") or {},
    )


def _encode(body: dict) -> str:
    return json.dumps(body, ensure_ascii=False, default=str)


def fit_body(body: dict) -> dict:
    """Remove itens do fim até o corpo caber no limite do Bedrock."""
    items = body.get("items")
    if not isinstance(items, list):
        return body
    body = {**body, "items": list(items)}
    while body["items"] and len(_encode(body).encode()) > MAX_BODY_BYTES:
        body["items"].pop()
        body["count"] = len(body["items"])
        body["truncated"] = True
    return body


def build_response(request: ActionRequest, status: int, body: dict) -> dict:
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": request.action_group,
            "apiPath": request.api_path,
            "httpMethod": request.http_method,
            "httpStatusCode": status,
            "responseBody": {"application/json": {"body": _encode(fit_body(body))}},
        },
        "sessionAttributes": request.session_attributes,
        "promptSessionAttributes": request.prompt_session_attributes,
    }
