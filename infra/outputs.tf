output "region" {
  value = var.region
}

# one() devolve null quando o count é 0, em vez de erro.
output "agent_id" {
  value = one(aws_bedrockagent_agent.this[*].agent_id)
}

output "agent_alias_id" {
  description = "Alias 'live'. Para desenvolvimento use TSTALIASID (DRAFT)."
  value       = one(aws_bedrockagent_agent_alias.live[*].agent_alias_id)
}

output "knowledge_base_id" {
  value = aws_bedrockagent_knowledge_base.docs.id
}

output "data_source_id" {
  value = aws_bedrockagent_data_source.docs.data_source_id
}

output "catalog_table" {
  value = aws_dynamodb_table.catalog.name
}

output "docs_bucket" {
  value = aws_s3_bucket.docs.bucket
}

output "catalog_action_function" {
  value = aws_lambda_function.catalog_action.function_name
}

output "docs_search_function" {
  value = aws_lambda_function.docs_search.function_name
}

output "gateway_id" {
  value = aws_bedrockagentcore_gateway.tools.gateway_id
}

output "gateway_url" {
  description = "Endpoint MCP do Gateway (auth IAM)."
  value       = aws_bedrockagentcore_gateway.tools.gateway_url
}
