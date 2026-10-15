# Uma role por componente, cada uma com só as ações e os recursos que usa.
# Sem curinga de ação e sem Resource "*".

# --- Agente -------------------------------------------------------------------

data "aws_iam_policy_document" "agent_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }

    # Impede que outra conta use esta role pelo serviço (confused deputy).
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:${local.partition}:bedrock:${var.region}:${local.account_id}:agent/*"]
    }
  }
}

data "aws_iam_policy_document" "agent" {
  statement {
    sid       = "InvokeFoundationModel"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = concat(local.foundation_model_arns, local.inference_profile_arns)
  }

  dynamic "statement" {
    for_each = local.uses_inference_profile ? [1] : []
    content {
      sid       = "UseInferenceProfile"
      actions   = ["bedrock:GetInferenceProfile"]
      resources = local.inference_profile_arns
    }
  }

  statement {
    sid       = "RetrieveFromKnowledgeBase"
    actions   = ["bedrock:Retrieve"]
    resources = [aws_bedrockagent_knowledge_base.docs.arn]
  }

  dynamic "statement" {
    for_each = var.enable_guardrail ? [1] : []
    content {
      sid       = "ApplyGuardrail"
      actions   = ["bedrock:ApplyGuardrail"]
      resources = [aws_bedrock_guardrail.this[0].guardrail_arn]
    }
  }
}

resource "aws_iam_role" "agent" {
  name               = "${local.name}-agent"
  assume_role_policy = data.aws_iam_policy_document.agent_trust.json
}

resource "aws_iam_role_policy" "agent" {
  name   = "agent"
  role   = aws_iam_role.agent.id
  policy = data.aws_iam_policy_document.agent.json
}

# --- Knowledge Base -----------------------------------------------------------

data "aws_iam_policy_document" "knowledge_base_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:${local.partition}:bedrock:${var.region}:${local.account_id}:knowledge-base/*"]
    }
  }
}

data "aws_iam_policy_document" "knowledge_base" {
  statement {
    sid       = "ListDocsBucket"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.docs.arn]
  }

  statement {
    sid       = "ReadDocs"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.docs.arn}/*"]
  }

  statement {
    sid       = "EmbedChunks"
    actions   = ["bedrock:InvokeModel"]
    resources = [local.embedding_model_arn]
  }

  statement {
    sid = "ReadWriteVectorIndex"
    actions = [
      "s3vectors:GetIndex",
      "s3vectors:PutVectors",
      "s3vectors:GetVectors",
      "s3vectors:DeleteVectors",
      "s3vectors:QueryVectors",
    ]
    resources = [aws_s3vectors_index.kb.index_arn]
  }
}

resource "aws_iam_role" "knowledge_base" {
  name               = "${local.name}-knowledge-base"
  assume_role_policy = data.aws_iam_policy_document.knowledge_base_trust.json
}

resource "aws_iam_role_policy" "knowledge_base" {
  name   = "knowledge-base"
  role   = aws_iam_role.knowledge_base.id
  policy = data.aws_iam_policy_document.knowledge_base.json
}

# --- Lambdas ------------------------------------------------------------------

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# Catálogo: só Query na tabela. Sem Scan, sem escrita. O modelo escolhe os
# parâmetros desta Lambda, então ela nunca deve ter uma credencial que escreve.
data "aws_iam_policy_document" "catalog_action" {
  statement {
    sid       = "QueryCatalog"
    actions   = ["dynamodb:Query"]
    resources = [aws_dynamodb_table.catalog.arn]
  }

  statement {
    sid       = "WriteOwnLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.catalog_action.arn}:*"]
  }
}

resource "aws_iam_role" "catalog_action" {
  name               = "${local.name}-catalog-action"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy" "catalog_action" {
  name   = "catalog-action"
  role   = aws_iam_role.catalog_action.id
  policy = data.aws_iam_policy_document.catalog_action.json
}

data "aws_iam_policy_document" "kb_ingest" {
  count = var.enable_auto_ingestion ? 1 : 0

  statement {
    sid       = "StartIngestion"
    actions   = ["bedrock:StartIngestionJob"]
    resources = [aws_bedrockagent_knowledge_base.docs.arn]
  }

  statement {
    sid       = "WriteOwnLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.kb_ingest[0].arn}:*"]
  }
}

resource "aws_iam_role" "kb_ingest" {
  count              = var.enable_auto_ingestion ? 1 : 0
  name               = "${local.name}-kb-ingest"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy" "kb_ingest" {
  count  = var.enable_auto_ingestion ? 1 : 0
  name   = "kb-ingest"
  role   = aws_iam_role.kb_ingest[0].id
  policy = data.aws_iam_policy_document.kb_ingest[0].json
}
