"""Conversa com o agente publicado e extrai do trace quais ferramentas ele chamou."""

import json
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# Alias de teste do Bedrock: aponta para a versão DRAFT, sempre a mais recente.
DRAFT_ALIAS_ID = "TSTALIASID"
INFRA_DIR = Path(__file__).resolve().parents[2] / "infra"


@dataclass
class ToolCall:
    kind: str  # "action" ou "knowledge_base"
    name: str  # apiPath da ação, ou "knowledge_base"
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentTurn:
    text: str
    tool_calls: list[ToolCall]
    session_id: str


def terraform_outputs(infra_dir: Path = INFRA_DIR) -> dict[str, str]:
    raw = subprocess.run(
        ["terraform", f"-chdir={infra_dir}", "output", "-json"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {k: v["value"] for k, v in json.loads(raw).items()}


def _collect_tool_calls(trace: dict, calls: list[ToolCall]) -> None:
    invocation = (trace.get("orchestrationTrace") or {}).get("invocationInput") or {}
    if action := invocation.get("actionGroupInvocationInput"):
        params = {p["name"]: str(p.get("value", "")) for p in action.get("parameters") or []}
        calls.append(ToolCall("action", action.get("apiPath", ""), params))
    if lookup := invocation.get("knowledgeBaseLookupInput"):
        calls.append(
            ToolCall("knowledge_base", "knowledge_base", {"query": lookup.get("text", "")})
        )


def ask(
    question: str,
    agent_id: str,
    alias_id: str = DRAFT_ALIAS_ID,
    session_id: str | None = None,
    region: str | None = None,
) -> AgentTurn:
    import boto3

    session_id = session_id or str(uuid.uuid4())
    runtime = boto3.client("bedrock-agent-runtime", region_name=region)
    response = runtime.invoke_agent(
        agentId=agent_id,
        agentAliasId=alias_id,
        sessionId=session_id,
        inputText=question,
        enableTrace=True,
    )
    text_parts: list[str] = []
    calls: list[ToolCall] = []
    for event in response["completion"]:
        if "chunk" in event:
            text_parts.append(event["chunk"]["bytes"].decode("utf-8"))
        elif "trace" in event:
            _collect_tool_calls(event["trace"].get("trace", {}), calls)
    return AgentTurn("".join(text_parts), calls, session_id)
