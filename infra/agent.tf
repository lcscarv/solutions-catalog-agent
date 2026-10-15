# Bedrock Agents Classic: em maintenance mode desde 2026-07-30, conta sem uso
# prévio recebe 403 no CreateAgent. Por isso o agente e o que depende dele
# ficam atrás de var.enable_agent. O substituto é o AgentCore.
resource "aws_bedrockagent_agent" "this" {
  count = var.enable_agent ? 1 : 0

  agent_name                  = "${local.name}-agent"
  description                 = "Assistente do catálogo de soluções para vendas e pré-vendas."
  agent_resource_role_arn     = aws_iam_role.agent.arn
  foundation_model            = var.foundation_model
  instruction                 = file("${path.root}/../prompts/agent_instruction.md")
  idle_session_ttl_in_seconds = 600
  prepare_agent               = true

  dynamic "guardrail_configuration" {
    for_each = var.enable_guardrail ? [1] : []
    content {
      guardrail_identifier = aws_bedrock_guardrail.this[0].guardrail_id
      guardrail_version    = aws_bedrock_guardrail_version.this[0].version
    }
  }

  depends_on = [aws_iam_role_policy.agent]
}

resource "aws_bedrockagent_agent_knowledge_base_association" "docs" {
  count = var.enable_agent ? 1 : 0

  agent_id             = aws_bedrockagent_agent.this[0].agent_id
  agent_version        = "DRAFT"
  knowledge_base_id    = aws_bedrockagent_knowledge_base.docs.id
  knowledge_base_state = "ENABLED"
  description          = trimspace(file("${path.root}/../prompts/knowledge_base_description.md"))
}

resource "aws_bedrockagent_agent_action_group" "catalog" {
  count = var.enable_agent ? 1 : 0

  agent_id                   = aws_bedrockagent_agent.this[0].agent_id
  agent_version              = "DRAFT"
  action_group_name          = "catalog"
  description                = "Busca somente leitura no catálogo: cases, materiais estratégicos e de suporte."
  action_group_state         = "ENABLED"
  skip_resource_in_use_check = true
  prepare_agent              = true

  action_group_executor {
    lambda = aws_lambda_function.catalog_action.arn
  }

  api_schema {
    payload = file("${path.root}/../contracts/catalog_api.yaml")
  }

  # Criado depois da associação da KB, para o prepare deste recurso já incluir
  # a KB. Mudanças só na associação pedem `make prepare`.
  depends_on = [
    aws_bedrockagent_agent_knowledge_base_association.docs,
    aws_lambda_permission.bedrock_invoke_catalog_action,
  ]
}

# Alias estável para consumidores (Slack, front). O alias congela uma versão
# no momento em que é criado. Para publicar mudanças: `make release`.
# Para desenvolver, use o alias de teste TSTALIASID, que aponta para DRAFT.
resource "aws_bedrockagent_agent_alias" "live" {
  count = var.enable_agent ? 1 : 0

  agent_id         = aws_bedrockagent_agent.this[0].agent_id
  agent_alias_name = "live"
  description      = "Versão publicada."

  depends_on = [aws_bedrockagent_agent_action_group.catalog]
}

# --- Guardrail (opcional) -----------------------------------------------------

resource "aws_bedrock_guardrail" "this" {
  count = var.enable_guardrail ? 1 : 0

  name                      = "${local.name}-guardrail"
  description               = "Bloqueia prompt injection e anonimiza contato pessoal."
  blocked_input_messaging   = "Não posso processar esse pedido."
  blocked_outputs_messaging = "Não posso responder isso."

  # Documentos da KB podem carregar instruções injetadas.
  content_policy_config {
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
  }

  sensitive_information_policy_config {
    pii_entities_config {
      type   = "EMAIL"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "PHONE"
      action = "ANONYMIZE"
    }
  }
}

resource "aws_bedrock_guardrail_version" "this" {
  count         = var.enable_guardrail ? 1 : 0
  guardrail_arn = aws_bedrock_guardrail.this[0].guardrail_arn
  description   = "managed by terraform"
}
