terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }

  # State local por padrão: é um laboratório de uma pessoa.
  # Para state remoto com lock nativo do S3 (Terraform >= 1.10), copie
  # backend.tf.example para backend.tf e rode `terraform init -migrate-state`.
}
