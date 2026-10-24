TF := terraform -chdir=infra
# PYTHONPATH explícito: ver o comentário em pyproject.toml (pythonpath).
PY := PYTHONPATH=src uv run python

.PHONY: help install up down seed-local test test-all lint fmt invoke \
        tf-init tf-plan tf-apply tf-destroy seed-aws sync-kb retrieve tools tool \
        prepare release chat eval

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-12s %s\n", $$1, $$2}'

# --- Local (grátis) -----------------------------------------------------------
install: ## instala dependências Python (uv)
	uv sync

up: ## sobe o DynamoDB Local
	docker compose up -d

down: ## derruba o DynamoDB Local
	docker compose down

seed-local: ## carrega o catálogo no DynamoDB Local
	$(PY) scripts/seed_catalog.py --local

test: ## testes unitários e de contrato
	uv run pytest -m "not integration"

test-all: ## inclui integração com o DynamoDB Local
	uv run pytest

lint: ## ruff + terraform fmt/validate
	uv run ruff check .
	uv run ruff format --check .
	$(TF) fmt -check -recursive
	$(TF) validate

fmt: ## formata Python e Terraform
	uv run ruff check --fix .
	uv run ruff format .
	$(TF) fmt -recursive

invoke: ## chama a Lambda localmente. Ex.: make invoke ARGS="/case-studies industry=Retail"
	$(PY) scripts/invoke_local.py $(or $(ARGS),/case-studies industry=Retail)

# --- AWS (custa centavos) -----------------------------------------------------
tf-init: ## terraform init
	$(TF) init

tf-plan: ## terraform plan
	$(TF) plan

tf-apply: ## cria ou atualiza a infraestrutura
	$(TF) apply

seed-aws: ## carrega o catálogo na tabela da AWS
	$(PY) scripts/seed_catalog.py

sync-kb: ## ingestão manual da KB, espera terminar
	$(PY) scripts/agent_ops.py sync-kb

retrieve: ## busca direto na KB, sem agente. Ex.: make retrieve Q="case de varejo"
	$(PY) scripts/agent_ops.py retrieve "$(Q)"

tools: ## lista as tools do Gateway (MCP direto, sem agente)
	$(PY) scripts/gateway_call.py list

tool: ## chama uma tool do Gateway. Ex.: make tool T=docs___search_documents A='{"query":"varejo"}'
	$(PY) scripts/gateway_call.py call "$(T)" '$(or $(A),{})'

prepare: ## recompila o DRAFT do agente
	$(PY) scripts/agent_ops.py prepare

release: ## publica o DRAFT atual numa nova versão do alias 'live'
	$(TF) apply -replace='aws_bedrockagent_agent_alias.live[0]'

chat: ## conversa com o agente (DRAFT)
	$(PY) scripts/chat.py

eval: ## roda o golden set contra o DRAFT
	$(PY) eval/run_eval.py

tf-destroy: ## apaga tudo na AWS
	$(TF) destroy
