# Empacota o pacote Python preservando o diretório, para o handler ser
# catalog_action.handler.lambda_handler e os imports relativos funcionarem.
data "archive_file" "catalog_action" {
  type        = "zip"
  output_path = "${path.module}/build/catalog_action.zip"

  dynamic "source" {
    for_each = fileset("${local.src_dir}/catalog_action", "*.py")
    content {
      content  = file("${local.src_dir}/catalog_action/${source.value}")
      filename = "catalog_action/${source.value}"
    }
  }
}

resource "aws_cloudwatch_log_group" "catalog_action" {
  name              = "/aws/lambda/${local.name}-catalog-action"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "catalog_action" {
  function_name    = "${local.name}-catalog-action"
  description      = "Executor do action group do catálogo (somente leitura)."
  role             = aws_iam_role.catalog_action.arn
  runtime          = "python3.12"
  architectures    = ["arm64"]
  handler          = "catalog_action.handler.lambda_handler"
  filename         = data.archive_file.catalog_action.output_path
  source_code_hash = data.archive_file.catalog_action.output_base64sha256
  timeout          = 10
  memory_size      = 256

  environment {
    variables = {
      CATALOG_TABLE = aws_dynamodb_table.catalog.name
      LOG_LEVEL     = "INFO"
    }
  }

  logging_config {
    log_format = "JSON"
    log_group  = aws_cloudwatch_log_group.catalog_action.name
  }
}

# A condição é o ARN do agente, que é o que o Bedrock envia como SourceArn.
resource "aws_lambda_permission" "bedrock_invoke_catalog_action" {
  statement_id   = "AllowBedrockAgentInvoke"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.catalog_action.function_name
  principal      = "bedrock.amazonaws.com"
  source_account = local.account_id
  source_arn     = aws_bedrockagent_agent.this.agent_arn
}
