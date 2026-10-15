"""Comparação de texto tolerante a caixa, acento e espaço."""

import unicodedata


def normalize(text: str) -> str:
    """'  Saúde ' -> 'saude'. Usado tanto no filtro quanto no valor do item."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_accents.casefold().split())


def field_contains(value: object, needle: str) -> bool:
    """True se o campo (texto ou lista de textos) contém o trecho já normalizado."""
    if isinstance(value, str):
        return needle in normalize(value)
    if isinstance(value, list | tuple | set):
        return any(isinstance(v, str) and needle in normalize(v) for v in value)
    return False
