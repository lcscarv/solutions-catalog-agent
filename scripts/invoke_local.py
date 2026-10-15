"""Simula a chamada que o agente faz à Lambda, contra o DynamoDB Local.

  uv run python scripts/invoke_local.py /case-studies industry=Retail limit=5

Útil para depurar a Lambda sem gastar token: é exatamente o evento que o
Bedrock envia, e a resposta é exatamente o que o modelo recebe.
"""

import json
import os
import sys

from catalog_action.handler import lambda_handler


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    api_path, *pairs = sys.argv[1:]
    params = [dict(zip(("name", "value"), p.split("=", 1), strict=True)) for p in pairs]

    os.environ.setdefault("DYNAMODB_ENDPOINT_URL", "http://localhost:8000")
    os.environ.setdefault("CATALOG_TABLE", "solutions-catalog-local")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "local")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local")

    event = {
        "messageVersion": "1.0",
        "actionGroup": "catalog",
        "apiPath": api_path,
        "httpMethod": "GET",
        "parameters": [{**p, "type": "string"} for p in params],
    }
    response = lambda_handler(event, None)
    inner = response["response"]
    body = json.loads(inner["responseBody"]["application/json"]["body"])
    print(f"HTTP {inner['httpStatusCode']}")
    print(json.dumps(body, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
