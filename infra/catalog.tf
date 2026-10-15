# Catálogo estruturado. Substitui o Postgres/PostgREST externo do original:
# acesso por IAM (sem segredo) e modo provisionado, que entra no free tier.
# Os dados são carregados por `make seed-aws`, não pelo Terraform: dado não é infra.
resource "aws_dynamodb_table" "catalog" {
  name           = "${local.name}-catalog"
  billing_mode   = "PROVISIONED"
  read_capacity  = var.catalog_read_capacity
  write_capacity = 1
  hash_key       = "asset_type"
  range_key      = "asset_id"

  attribute {
    name = "asset_type"
    type = "S"
  }

  attribute {
    name = "asset_id"
    type = "S"
  }
}
