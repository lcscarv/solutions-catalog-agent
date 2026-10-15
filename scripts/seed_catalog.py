"""Carrega data/catalog.json no DynamoDB.

Local (DynamoDB Local, cria a tabela):  uv run python scripts/seed_catalog.py --local
AWS (tabela criada pelo Terraform):     uv run python scripts/seed_catalog.py
"""

import argparse
import json
import os
from pathlib import Path

import boto3

from agent_client.client import terraform_outputs

ROOT = Path(__file__).resolve().parents[1]
LOCAL_ENDPOINT = "http://localhost:8000"
LOCAL_TABLE = "solutions-catalog-local"


def create_local_table(resource, name: str):
    existing = {t.name for t in resource.tables.all()}
    if name in existing:
        return resource.Table(name)
    table = resource.create_table(
        TableName=name,
        KeySchema=[
            {"AttributeName": "asset_type", "KeyType": "HASH"},
            {"AttributeName": "asset_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "asset_type", "AttributeType": "S"},
            {"AttributeName": "asset_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true", help="usa o DynamoDB Local")
    parser.add_argument("--table", help="nome da tabela (padrão: saída do Terraform)")
    args = parser.parse_args()

    if args.local:
        # O DynamoDB Local aceita qualquer credencial.
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "local")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local")
        resource = boto3.resource("dynamodb", endpoint_url=LOCAL_ENDPOINT, region_name="us-east-1")
        table = create_local_table(resource, args.table or LOCAL_TABLE)
    else:
        outputs = terraform_outputs()
        resource = boto3.resource("dynamodb", region_name=outputs["region"])
        table = resource.Table(args.table or outputs["catalog_table"])

    items = json.loads((ROOT / "data" / "catalog.json").read_text())
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
    print(f"{len(items)} itens gravados em {table.name}")


if __name__ == "__main__":
    main()
