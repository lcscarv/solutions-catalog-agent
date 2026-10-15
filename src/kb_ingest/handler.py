"""Entrada da Lambda. Handler: kb_ingest.handler.lambda_handler.

Disparada por evento do S3. Só um ingestion job roda por data source de cada
vez: se já houver um em andamento, o Bedrock responde ConflictException e nós
ignoramos. Um arquivo enviado durante um job em andamento entra no próximo sync
(próximo upload ou `make sync-kb`). Para garantir, o passo seguinte seria uma
fila SQS com atraso fazendo debounce.
"""

import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_client = None


def _bedrock_agent():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-agent")
    return _client


def lambda_handler(event: dict, context: object) -> dict:
    keys = [r["s3"]["object"]["key"] for r in event.get("Records", []) if "s3" in r]
    logger.info("documents changed", extra={"keys": keys})
    try:
        job = _bedrock_agent().start_ingestion_job(
            knowledgeBaseId=os.environ["KNOWLEDGE_BASE_ID"],
            dataSourceId=os.environ["DATA_SOURCE_ID"],
            description=f"auto: {len(keys)} object(s) changed",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConflictException":
            logger.info("ingestion already running, skipping")
            return {"status": "skipped"}
        raise
    job_id = job["ingestionJob"]["ingestionJobId"]
    logger.info("ingestion started", extra={"ingestion_job_id": job_id})
    return {"status": "started", "ingestion_job_id": job_id}
