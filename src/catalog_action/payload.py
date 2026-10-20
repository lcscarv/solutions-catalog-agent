"""Limite de tamanho da resposta, comum aos dois formatos de entrada.

O controle principal de tamanho é o `limit` com a projeção de campos (routes.py):
com eles, 25 itens ficam bem abaixo deste limite. O corte aqui é rede de
segurança. Se disparar, a projeção ou o limit estão errados, e o log avisa.
"""

import json
import logging

logger = logging.getLogger(__name__)

# No Bedrock Agents, respostas de action group acima de cerca de 25 KB são
# rejeitadas. No Gateway não verificamos um limite da API: aqui o número é
# orçamento de contexto, porque o resultado da tool fica no contexto do modelo.
MAX_BODY_BYTES = 20_000

# Resultado parcial não é erro: o modelo mostra o que veio e oferece um filtro.
TRUNCATED_NOTE = (
    "Only part of the matches is shown (count of total_matches). Tell the user "
    "and offer to narrow the search with a filter."
)


def encode(body: dict) -> str:
    return json.dumps(body, ensure_ascii=False, default=str)


def fit_body(body: dict) -> dict:
    """Remove itens do fim até o corpo caber no limite."""
    items = body.get("items")
    if not isinstance(items, list):
        return body
    body = {**body, "items": list(items)}
    while body["items"] and len(encode(body).encode()) > MAX_BODY_BYTES:
        body["items"].pop()
        # Tudo o que o corte acrescenta entra na medida da próxima volta.
        body["count"] = len(body["items"])
        body["truncated"] = True
        body.setdefault("note", TRUNCATED_NOTE)
    if removed := len(items) - len(body["items"]):
        logger.warning("response cut to fit", extra={"removed": removed, "kept": body["count"]})
    return body
