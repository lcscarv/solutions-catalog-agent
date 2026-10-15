"""Acesso ao catálogo. O handler depende do protocolo, não do DynamoDB."""

import os
from typing import Protocol


class CatalogError(Exception):
    """O catálogo não respondeu. Vira 503 para o agente, nunca lista vazia."""


class Catalog(Protocol):
    def list_assets(self, asset_type: str) -> list[dict]: ...


class InMemoryCatalog:
    """Para testes e para rodar o handler sem banco nenhum."""

    def __init__(self, items: list[dict]):
        self._items = items

    def list_assets(self, asset_type: str) -> list[dict]:
        return [i for i in self._items if i.get("asset_type") == asset_type]


class DynamoCatalog:
    """Tabela com chave (asset_type, asset_id).

    Cada tipo de ativo é uma partição, então a busca é um Query numa partição e
    o filtro textual roda em Python. Serve para centenas de itens; com milhares,
    o filtro iria para um GSI ou para um índice de busca.
    """

    def __init__(self, table):
        self._table = table

    @classmethod
    def from_env(cls) -> "DynamoCatalog":
        import boto3
        from botocore.config import Config

        config = Config(
            connect_timeout=2,
            read_timeout=5,
            retries={"max_attempts": 3, "mode": "standard"},
        )
        endpoint = os.environ.get("DYNAMODB_ENDPOINT_URL") or None
        resource = boto3.resource("dynamodb", endpoint_url=endpoint, config=config)
        return cls(resource.Table(os.environ["CATALOG_TABLE"]))

    def list_assets(self, asset_type: str) -> list[dict]:
        from boto3.dynamodb.conditions import Key
        from botocore.exceptions import BotoCoreError, ClientError

        kwargs = {"KeyConditionExpression": Key("asset_type").eq(asset_type)}
        items: list[dict] = []
        try:
            while True:
                page = self._table.query(**kwargs)
                items.extend(page["Items"])
                if "LastEvaluatedKey" not in page:
                    return items
                kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        except (BotoCoreError, ClientError) as exc:
            raise CatalogError(str(exc)) from exc
