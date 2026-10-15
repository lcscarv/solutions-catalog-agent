# --- Documentos de origem -----------------------------------------------------

resource "aws_s3_bucket" "docs" {
  bucket_prefix = "${local.name}-docs-"
  force_destroy = true # laboratório: `terraform destroy` limpa tudo
}

resource "aws_s3_bucket_public_access_block" "docs" {
  bucket                  = aws_s3_bucket.docs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "docs" {
  bucket = aws_s3_bucket.docs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Documentos e seus .metadata.json. Os metadados permitem filtrar a busca
# vetorial por indústria e solução.
resource "aws_s3_object" "docs" {
  for_each = fileset(local.docs_dir, "**")

  bucket       = aws_s3_bucket.docs.id
  key          = each.value
  source       = "${local.docs_dir}/${each.value}"
  etag         = filemd5("${local.docs_dir}/${each.value}")
  content_type = endswith(each.value, ".json") ? "application/json" : "text/markdown"

  # Sobe depois da notificação, para o próprio apply disparar a ingestão.
  depends_on = [aws_s3_bucket_notification.docs]
}

# --- Vector store -------------------------------------------------------------

resource "aws_s3vectors_vector_bucket" "kb" {
  vector_bucket_name = "${local.name}-vectors"
  force_destroy      = true
}

resource "aws_s3vectors_index" "kb" {
  index_name         = "docs"
  vector_bucket_name = aws_s3vectors_vector_bucket.kb.vector_bucket_name
  data_type          = "float32"
  dimension          = var.embedding_dimensions
  distance_metric    = "cosine"

  # A KB guarda o texto do chunk como metadado do vetor. Metadado filtrável tem
  # limite de tamanho no S3 Vectors, então o texto precisa ser não filtrável,
  # senão a ingestão de chunks maiores falha.
  metadata_configuration {
    non_filterable_metadata_keys = ["AMAZON_BEDROCK_TEXT", "AMAZON_BEDROCK_METADATA"]
  }
}

# --- Knowledge Base -----------------------------------------------------------

resource "aws_bedrockagent_knowledge_base" "docs" {
  name        = "${local.name}-docs"
  description = "Texto completo dos materiais do catálogo."
  role_arn    = aws_iam_role.knowledge_base.arn

  knowledge_base_configuration {
    type = "VECTOR"

    vector_knowledge_base_configuration {
      embedding_model_arn = local.embedding_model_arn

      embedding_model_configuration {
        bedrock_embedding_model_configuration {
          dimensions          = var.embedding_dimensions
          embedding_data_type = "FLOAT32"
        }
      }
    }
  }

  storage_configuration {
    type = "S3_VECTORS"

    s3_vectors_configuration {
      index_arn = aws_s3vectors_index.kb.index_arn
    }
  }

  depends_on = [aws_iam_role_policy.knowledge_base]
}

resource "aws_bedrockagent_data_source" "docs" {
  knowledge_base_id    = aws_bedrockagent_knowledge_base.docs.id
  name                 = "docs-s3"
  data_deletion_policy = "DELETE"

  data_source_configuration {
    type = "S3"

    s3_configuration {
      bucket_arn = aws_s3_bucket.docs.arn
    }
  }

  # Chunking explícito, em vez do default implícito do original.
  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "FIXED_SIZE"

      fixed_size_chunking_configuration {
        max_tokens         = var.chunk_max_tokens
        overlap_percentage = var.chunk_overlap_percentage
      }
    }
  }
}

# --- Ingestão automática ------------------------------------------------------

data "archive_file" "kb_ingest" {
  type        = "zip"
  output_path = "${path.module}/build/kb_ingest.zip"

  dynamic "source" {
    for_each = fileset("${local.src_dir}/kb_ingest", "*.py")
    content {
      content  = file("${local.src_dir}/kb_ingest/${source.value}")
      filename = "kb_ingest/${source.value}"
    }
  }
}

resource "aws_cloudwatch_log_group" "kb_ingest" {
  count             = var.enable_auto_ingestion ? 1 : 0
  name              = "/aws/lambda/${local.name}-kb-ingest"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "kb_ingest" {
  count = var.enable_auto_ingestion ? 1 : 0

  function_name    = "${local.name}-kb-ingest"
  description      = "Dispara a sincronização da KB quando um documento muda."
  role             = aws_iam_role.kb_ingest[0].arn
  runtime          = "python3.12"
  architectures    = ["arm64"]
  handler          = "kb_ingest.handler.lambda_handler"
  filename         = data.archive_file.kb_ingest.output_path
  source_code_hash = data.archive_file.kb_ingest.output_base64sha256
  timeout          = 10

  environment {
    variables = {
      KNOWLEDGE_BASE_ID = aws_bedrockagent_knowledge_base.docs.id
      DATA_SOURCE_ID    = aws_bedrockagent_data_source.docs.data_source_id
    }
  }

  logging_config {
    log_format = "JSON"
    log_group  = aws_cloudwatch_log_group.kb_ingest[0].name
  }
}

resource "aws_lambda_permission" "s3_invoke_kb_ingest" {
  count = var.enable_auto_ingestion ? 1 : 0

  statement_id   = "AllowDocsBucketInvoke"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.kb_ingest[0].function_name
  principal      = "s3.amazonaws.com"
  source_arn     = aws_s3_bucket.docs.arn
  source_account = local.account_id
}

resource "aws_s3_bucket_notification" "docs" {
  count  = var.enable_auto_ingestion ? 1 : 0
  bucket = aws_s3_bucket.docs.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.kb_ingest[0].arn
    events              = ["s3:ObjectCreated:*", "s3:ObjectRemoved:*"]
  }

  depends_on = [aws_lambda_permission.s3_invoke_kb_ingest]
}
