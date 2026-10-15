variable "project" {
  description = "Prefixo dos nomes de recurso."
  type        = string
  default     = "solutions-catalog"
}

variable "environment" {
  description = "Nome do ambiente (dev, prd). Cada ambiente é um state separado."
  type        = string
  default     = "dev"
}

variable "region" {
  description = "Região AWS. us-east-1 tem a maior oferta de modelos no Bedrock."
  type        = string
  default     = "us-east-1"
}

variable "foundation_model" {
  description = "Modelo do agente. O prefixo 'us.' indica um cross-region inference profile."
  type        = string
  default     = "us.amazon.nova-lite-v1:0"
}

variable "embedding_model_id" {
  description = "Modelo de embedding da Knowledge Base."
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

variable "embedding_dimensions" {
  description = "Dimensão do embedding. Tem que ser a mesma no índice vetorial e na KB."
  type        = number
  default     = 1024

  validation {
    condition     = contains([256, 512, 1024], var.embedding_dimensions)
    error_message = "Titan Text Embeddings v2 aceita 256, 512 ou 1024 dimensões."
  }
}

variable "chunk_max_tokens" {
  description = "Tamanho máximo de cada chunk na ingestão da KB."
  type        = number
  default     = 300
}

variable "chunk_overlap_percentage" {
  description = "Sobreposição entre chunks consecutivos, em porcentagem."
  type        = number
  default     = 20
}

variable "enable_auto_ingestion" {
  description = "Sincroniza a KB automaticamente quando um documento muda no S3."
  type        = bool
  default     = true
}

variable "enable_agent" {
  description = "Cria o agente Bedrock Agents Classic. Contas sem uso prévio recebem 403 no CreateAgent (maintenance mode desde 2026-07-30)."
  type        = bool
  default     = false
}

variable "enable_guardrail" {
  description = "Liga um Bedrock Guardrail (prompt attack e PII). Cobra por texto avaliado."
  type        = bool
  default     = false
}

variable "catalog_read_capacity" {
  description = "RCU provisionadas da tabela. O free tier cobre até 25 no total da conta."
  type        = number
  default     = 2
}

variable "log_retention_days" {
  description = "Retenção dos logs das Lambdas."
  type        = number
  default     = 7
}

variable "budget_email" {
  description = "E-mail para alerta de custo. Vazio desliga o budget."
  type        = string
  default     = ""
}

variable "budget_limit_usd" {
  description = "Teto mensal do alerta de custo, em dólares."
  type        = number
  default     = 5
}
