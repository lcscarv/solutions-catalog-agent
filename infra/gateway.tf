# AgentCore Gateway: um endpoint MCP que expõe as Lambdas como tools.
# Auth de entrada por IAM (SigV4): quem chama precisa de
# bedrock-agentcore:InvokeGateway. O harness vai usar a própria role.
resource "aws_bedrockagentcore_gateway" "tools" {
  name            = "${local.name}-tools"
  description     = "Tools do catálogo e da busca em documentos."
  role_arn        = aws_iam_role.gateway.arn
  authorizer_type = "AWS_IAM"
  protocol_type   = "MCP"
}

locals {
  # Um target por Lambda. O nome do target vira prefixo da tool:
  # "catalog___search_case_studies". As Lambdas removem o prefixo.
  gateway_targets = {
    catalog = {
      description = "Busca estruturada no catálogo (DynamoDB)."
      lambda_arn  = aws_lambda_function.catalog_action.arn
      tools       = jsondecode(file("${path.root}/../contracts/catalog_tools.json"))
    }
    docs = {
      description = "Busca semântica no texto dos documentos (Knowledge Base)."
      lambda_arn  = aws_lambda_function.docs_search.arn
      tools       = jsondecode(file("${path.root}/../contracts/docs_tools.json"))
    }
  }
}

# O contrato fica num arquivo JSON só (testado em tests/test_contract.py);
# os blocos de schema são gerados a partir dele, em vez de repetidos em HCL.
resource "aws_bedrockagentcore_gateway_target" "lambda" {
  for_each = local.gateway_targets

  name               = each.key
  description        = each.value.description
  gateway_identifier = aws_bedrockagentcore_gateway.tools.gateway_id

  # O Gateway invoca a Lambda com a role dele (aws_iam_role.gateway).
  credential_provider_configuration {
    gateway_iam_role {}
  }

  target_configuration {
    mcp {
      lambda {
        lambda_arn = each.value.lambda_arn

        tool_schema {
          dynamic "inline_payload" {
            for_each = each.value.tools
            content {
              name        = inline_payload.value.name
              description = inline_payload.value.description

              input_schema {
                type = "object"

                dynamic "property" {
                  for_each = inline_payload.value.inputSchema.properties
                  content {
                    name        = property.key
                    type        = property.value.type
                    description = property.value.description
                    required    = contains(try(inline_payload.value.inputSchema.required, []), property.key)
                  }
                }
              }
            }
          }
        }
      }
    }
  }

  # O Gateway pode validar o acesso à Lambda ao criar o target; a policy que
  # dá esse acesso não é referenciada aqui, só a role pelo gateway.
  depends_on = [aws_iam_role_policy.gateway]
}
