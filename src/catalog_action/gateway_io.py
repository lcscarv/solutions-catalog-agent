"""Formato de entrada e saída do AgentCore Gateway para targets Lambda.

O Gateway manda só os argumentos da tool como evento. O nome da tool vem no
client context, prefixado pelo nome do target: "catalog___search_case_studies".
Não há envelope nem status HTTP: a resposta é o próprio JSON que o modelo lê,
e erro é um corpo com "error" e uma mensagem que diz ao modelo o que fazer.
"""

DELIMITER = "___"


def tool_name(context: object) -> str:
    """Nome da tool sem o prefixo do target, ou "" se não veio do Gateway."""
    client_context = getattr(context, "client_context", None)
    custom = getattr(client_context, "custom", None) or {}
    full = custom.get("bedrockAgentCoreToolName", "")
    return full.split(DELIMITER, 1)[-1]


def parse_params(event: dict | None) -> dict[str, str]:
    # O modelo pode mandar número ou null; a lógica de busca trabalha com texto.
    return {k: str(v) for k, v in (event or {}).items() if v is not None}
