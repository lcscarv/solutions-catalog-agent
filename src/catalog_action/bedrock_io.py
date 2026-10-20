"""Formato de entrada e saída do Bedrock Agents para Action Groups com OpenAPI."""

from dataclasses import dataclass, field

from .payload import encode, fit_body


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


def build_response(request: ActionRequest, status: int, body: dict) -> dict:
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": request.action_group,
            "apiPath": request.api_path,
            "httpMethod": request.http_method,
            "httpStatusCode": status,
            "responseBody": {"application/json": {"body": encode(fit_body(body))}},
        },
        "sessionAttributes": request.session_attributes,
        "promptSessionAttributes": request.prompt_session_attributes,
    }
