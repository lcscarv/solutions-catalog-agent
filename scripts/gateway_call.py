"""Fala MCP direto com o AgentCore Gateway, sem agente, para validar as tools.

  uv run python scripts/gateway_call.py list
  uv run python scripts/gateway_call.py call docs___search_documents '{"query": "varejo"}'

Assina a requisição com SigV4 usando a credencial local (AWS_PROFILE), do mesmo
jeito que o harness vai assinar com a role dele. Não depende do AWS CLI.
"""

import json
import sys
import urllib.error
import urllib.request

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from agent_client.client import terraform_outputs

SERVICE = "bedrock-agentcore"


def mcp_request(url: str, region: str, method: str, params: dict | None = None) -> dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        # MCP streamable HTTP: o servidor pode responder JSON ou SSE.
        "Accept": "application/json, text/event-stream",
    }
    request = AWSRequest(method="POST", url=url, data=body, headers=headers)
    credentials = boto3.Session().get_credentials().get_frozen_credentials()
    SigV4Auth(credentials, SERVICE, region).add_auth(request)

    http = urllib.request.Request(url, data=body, headers=dict(request.headers), method="POST")
    try:
        with urllib.request.urlopen(http, timeout=60) as response:
            raw = response.read().decode()
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        sys.exit(f"HTTP {exc.code}: {exc.read().decode()}")

    if content_type.startswith("text/event-stream"):
        data = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")]
        raw = data[-1] if data else "{}"
    message = json.loads(raw)
    if "error" in message:
        sys.exit(f"erro MCP: {json.dumps(message['error'], ensure_ascii=False)}")
    return message["result"]


def list_tools(url: str, region: str) -> None:
    for tool in mcp_request(url, region, "tools/list")["tools"]:
        params = ", ".join(tool.get("inputSchema", {}).get("properties", {}))
        print(f"{tool['name']}({params})")


def call_tool(url: str, region: str, name: str, arguments: dict) -> None:
    result = mcp_request(url, region, "tools/call", {"name": name, "arguments": arguments})
    for block in result.get("content", []):
        text = block.get("text", "")
        try:
            print(json.dumps(json.loads(text), indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(text)
    if result.get("isError"):
        sys.exit(1)


def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ["list"] and len(args) == 1:
        command = "list"
    elif args[:1] == ["call"] and len(args) in (2, 3):
        command = "call"
    else:
        sys.exit(__doc__)

    outputs = terraform_outputs()
    url, region = outputs["gateway_url"], outputs["region"]
    if command == "list":
        list_tools(url, region)
    else:
        call_tool(url, region, args[1], json.loads(args[2]) if len(args) == 3 else {})


if __name__ == "__main__":
    main()
