"""Operações no agente e na KB que o Terraform não cobre bem.

  uv run python scripts/agent_ops.py prepare   # recompila o DRAFT do agente
  uv run python scripts/agent_ops.py sync-kb   # ingestão manual da KB e espera terminar

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


COMMANDS = {"prepare": prepare, "sync-kb": sync_kb}


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    outputs = terraform_outputs()
    client = boto3.client("bedrock-agent", region_name=outputs["region"])
    COMMANDS[sys.argv[1]](client, outputs)


if __name__ == "__main__":
    main()
