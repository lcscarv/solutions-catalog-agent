locals {
  name       = "${var.project}-${var.environment}"
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition

  src_dir  = "${path.root}/../src"
  docs_dir = "${path.root}/../data/docs"

  # "us.amazon.nova-lite-v1:0" -> "amazon.nova-lite-v1:0"
  base_model_id          = replace(var.foundation_model, "/^(us|eu|apac|global)\\./", "")
  uses_inference_profile = local.base_model_id != var.foundation_model

  # Com inference profile, o agente precisa de permissão no profile e no modelo
  # em todas as regiões para onde o profile pode rotear a chamada.
  foundation_model_arns = ["arn:${local.partition}:bedrock:*::foundation-model/${local.base_model_id}"]
  inference_profile_arns = local.uses_inference_profile ? [
    "arn:${local.partition}:bedrock:${var.region}:${local.account_id}:inference-profile/${var.foundation_model}"
  ] : []

  embedding_model_arn = "arn:${local.partition}:bedrock:${var.region}::foundation-model/${var.embedding_model_id}"
}
