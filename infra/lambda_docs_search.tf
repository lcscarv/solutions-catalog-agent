# Tool search_documents do Gateway: Retrieve na KB com filtro de metadado.
# Lambda separada da do catálogo para cada uma ter só a permissão que usa.
data "archive_file" "docs_search" {
  type        = "zip"
  output_path = "${path.module}/build/docs_search.zip"

  dynamic "source" {
    for_each = fileset("${local.src_dir}/docs_search", "*.py")
    content {
      content  = file("${local.src_dir}/docs_search/${source.value}")
      filename = "docs_search/${source.value}"
    }
  }
}

resource "aws_cloudwatch_log_group" "docs_search" {
  name              = "/aws/lambda/${local.name}-docs-search"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "docs_search" {
  function_name    = "${local.name}-docs-search"
  description      = "Tool de busca semântica na KB (somente leitura)."
  role             = aws_iam_role.docs_search.arn
  runtime          = "python3.12"
  architectures    = ["arm64"]
  handler          = "docs_search.handler.lambda_handler"
  filename         = data.archive_file.docs_search.output_path
  source_code_hash = data.archive_file.docs_search.output_base64sha256
  timeout          = 15
  memory_size      = 256

  environment {
    variables = {
      KNOWLEDGE_BASE_ID = aws_bedrockagent_knowledge_base.docs.id
      LOG_LEVEL         = "INFO"
    }
  }

  logging_config {
    log_format = "JSON"
    log_group  = aws_cloudwatch_log_group.docs_search.name
  }
}
