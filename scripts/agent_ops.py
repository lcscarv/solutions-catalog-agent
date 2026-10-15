"""Operações no agente e na KB que o Terraform não cobre bem.

  uv run python scripts/agent_ops.py prepare   # recompila o DRAFT do agente
  uv run python scripts/agent_ops.py sync-kb   # ingestão manual da KB e espera terminar
  uv run python scripts/agent_ops.py retrieve "pergunta"   # busca direto na KB, sem agente

Não depende do AWS CLI: usa boto3, que já está no projeto.
"""

import sys
import time

import boto3

from agent_client.client import terraform_outputs


def prepare(client, outputs: dict) -> None:
    client.prepare_agent(agentId=outputs["agent_id"])
    while True:
        status = client.get_agent(agentId=outputs["agent_id"])["agent"]["agentStatus"]
        print(f"agente: {status}")
        if status in {"PREPARED", "FAILED", "NOT_PREPARED"}:
            return
        time.sleep(3)


def sync_kb(client, outputs: dict) -> None:
    ids = {
        "knowledgeBaseId": outputs["knowledge_base_id"],
        "dataSourceId": outputs["data_source_id"],
    }
    job_id = client.start_ingestion_job(**ids)["ingestionJob"]["ingestionJobId"]
    while True:
        job = client.get_ingestion_job(**ids, ingestionJobId=job_id)["ingestionJob"]
        print(f"ingestão: {job['status']} {job.get('statistics', {})}")
        if job["status"] in {"COMPLETE", "FAILED", "STOPPED"}:
            for reason in job.get("failureReasons", []):
                print(f"  falha: {reason}")
            return
        time.sleep(5)


def retrieve(outputs: dict, question: str, top: int = 5) -> None:
    """O mesmo Retrieve que o agente faria, para validar a KB isoladamente."""
    client = boto3.client("bedrock-agent-runtime", region_name=outputs["region"])
    results = client.retrieve(
        knowledgeBaseId=outputs["knowledge_base_id"],
        retrievalQuery={"text": question},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": top}},
    )["retrievalResults"]
    if not results:
        print("nenhum resultado: a ingestão já rodou? (make sync-kb)")
    for result in results:
        key = result["location"]["s3Location"]["uri"].split("/", 3)[-1]
        snippet = " ".join(result["content"]["text"].split())[:120]
        print(f"{result['score']:.3f}  {key}\n       {snippet}...")


COMMANDS = {"prepare": prepare, "sync-kb": sync_kb}


def main() -> None:
    command, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    if command == "retrieve":
        if not args or not " ".join(args).strip():
            sys.exit('uso: agent_ops.py retrieve "pergunta"')
        retrieve(terraform_outputs(), " ".join(args))
        return
    if command not in COMMANDS or args:
        sys.exit(__doc__)
    outputs = terraform_outputs()
    client = boto3.client("bedrock-agent", region_name=outputs["region"])
    COMMANDS[command](client, outputs)


if __name__ == "__main__":
    main()
