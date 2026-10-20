# Solutions Catalog Agent (laboratório)

Versão de estudo de um agente Amazon Bedrock que ajuda vendas e pré-vendas a
achar materiais: cases de clientes, sales decks, calculadoras de ROI e
templates. Refeita a partir de um projeto real para pôr em prática o que ele
tinha de fraco. Roda localmente o que dá para rodar localmente, e na AWS com
custo de centavos.

Todos os dados são fictícios.

## Arquitetura

```
Usuário (scripts/chat.py)
  │
  ▼
Bedrock Agent ── Nova Lite via inference profile us.
  │
  ├── Action Group "catalog" (OpenAPI, 3 GETs)
  │     └── Lambda catalog_action ── dynamodb:Query ──► DynamoDB (catálogo)
  │
  └── Knowledge Base
        └── S3 Vectors (índice 1024d, cosseno) ◄── Titan Embed v2 ◄── S3 (docs + metadados)
                                                                   ▲
                                         Lambda kb_ingest ─────────┘ (evento do S3 dispara o sync)
```

**Regra de desenho:** listas e links vêm do catálogo estruturado e nunca são
gerados pelo modelo. A KB entra só para detalhe de dentro de um documento.

## O que mudou em relação ao original

| Problema no original | Correção aqui | Onde |
|---|---|---|
| Handler declarado não batia com o arquivo empacotado | Handler `catalog_action.handler.lambda_handler`, zip montado preservando o pacote | [infra/lambda_action.tf](infra/lambda_action.tf) |
| Permissão da Lambda condicionada ao ARN da role, não do agente | `source_arn` = ARN do agente, mais `source_account` | [infra/lambda_action.tf](infra/lambda_action.tf) |
| Chave de banco com privilégio total numa variável de ambiente | DynamoDB acessado por IAM: a role só tem `dynamodb:Query` na tabela. Não existe segredo | [infra/iam.tf](infra/iam.tf) |
| IAM com curingas (`bedrock:*`, `lambda:*`, `s3vectors:*`) e `Resource: "*"` | Uma role por componente, ações enumeradas, recursos específicos, condições `SourceAccount`/`SourceArn` contra confused deputy | [infra/iam.tf](infra/iam.tf) |
| Bucket criado pelo Terraform diferente do usado pela KB | Um bucket só, referenciado por atributo, nunca por nome repetido | [infra/knowledge_base.tf](infra/knowledge_base.tf) |
| Módulo pre-1.0 exigindo provider OpenSearch dummy | Recursos nativos do provider AWS; cada peça visível | [infra/](infra/) |
| Erro da consulta virava lista vazia com 200 | 400, 404, 405 e 503 com mensagem para o modelo; 503 manda dizer que a busca falhou | [src/catalog_action/handler.py](src/catalog_action/handler.py) |
| Wildcard `%` cru na URL do PostgREST | Normalização em Python (caixa, acento, espaço); sem montagem de URL | [src/catalog_action/matching.py](src/catalog_action/matching.py) |
| `select=*` sem limite | `limit` de 1 a 25, projeção de campos e corte abaixo do limite de 25 KB do Bedrock, com `truncated` | [src/catalog_action/routes.py](src/catalog_action/routes.py), [bedrock_io.py](src/catalog_action/bedrock_io.py) |
| Parâmetro "industry" significava tag ou descrição conforme o endpoint | Nomes honestos (`industry`, `solution`, `tag`, `query`) e `enum` para o modelo mapear "varejo" para Retail | [contracts/catalog_api.yaml](contracts/catalog_api.yaml) |
| Schema e código podiam divergir | Teste de contrato: rotas, parâmetros e enums batem com o código e com os dados | [tests/test_contract.py](tests/test_contract.py) |
| Prompt duplicado e ambíguo | Instrução reescrita: roteamento explícito, nunca inventar link, como agir em erro e em resultado truncado | [prompts/agent_instruction.md](prompts/agent_instruction.md) |
| Log do evento inteiro, sem retenção | Log JSON só com nomes de parâmetro (o valor é texto do usuário); retenção de 7 dias | handler e [lambda_action.tf](infra/lambda_action.tf) |
| Ingestão da KB manual | Evento do S3 dispara `StartIngestionJob`; `make sync-kb` para forçar | [src/kb_ingest/](src/kb_ingest/) |
| Chunking implícito | Fixed-size explícito (300 tokens, 20%) e `.metadata.json` por documento para filtro | [knowledge_base.tf](infra/knowledge_base.tf), [data/docs/](data/docs/) |
| Texto do chunk como metadado filtrável no S3 Vectors | `AMAZON_BEDROCK_TEXT` e `AMAZON_BEDROCK_METADATA` como não filtráveis, senão chunks maiores falham | [knowledge_base.tf](infra/knowledge_base.tf) |
| Sem guardrails | Guardrail opcional: prompt attack (injeção via documento) e PII | [agent.tf](infra/agent.tf) |
| Sem alias nem versão | Alias `live` congelado; `make release` publica; desenvolvimento no `TSTALIASID` | [agent.tf](infra/agent.tf) |
| Sem avaliação | Golden set com ferramenta e parâmetros esperados, lidos do trace; `--repeat` mede variância | [eval/](eval/) |
| State sem lock, CI apontando para stacks inexistentes | `backend.tf.example` com `use_lockfile`; CI roda lint, testes com DynamoDB Local, `validate` e tflint | [infra/backend.tf.example](infra/backend.tf.example), [.github/workflows/ci.yml](.github/workflows/ci.yml) |
| Agente no Bedrock Agents (em maintenance mode desde 2026-07-30: conta nova não cria agente) | Migração para AgentCore: Gateway MCP com auth IAM expondo as Lambdas como tools; a mesma Lambda do catálogo atende os dois formatos | [infra/gateway.tf](infra/gateway.tf), [gateway_io.py](src/catalog_action/gateway_io.py) |
| KB consultada só pelo texto: um deck genérico vencia o case específico | Tool `search_documents` com filtro de metadado (`asset_type`, `industry`) escolhido pelo modelo | [src/docs_search/](src/docs_search/), [contracts/docs_tools.json](contracts/docs_tools.json) |
| Credenciais estáticas em `.env` | Use `aws configure sso` ou um perfil; nada de chave no repositório | abaixo |

## Custo

**O Bedrock não entra no free tier.** Ele cobra por token, assim como os
embeddings e o S3 Vectors. Para um laboratório, o gasto fica em centavos por
sessão de testes. O resto foi desenhado para caber no "always free".

| Serviço | Uso aqui | Free tier |
|---|---|---|
| Lambda | 3 funções, poucas invocações | Sim (1M req/mês) |
| AgentCore Gateway | US$ 0,005 por mil chamadas de tool | Não, mas centavos |
| DynamoDB | Tabela provisionada 2 RCU / 1 WCU | Sim (25 RCU/WCU, 25 GB) |
| CloudWatch Logs | Retenção de 7 dias | Sim (5 GB) |
| S3 | Alguns KB de documentos | Contas novas usam créditos do plano gratuito |
| S3 Vectors | Dezenas de vetores | Não, mas centavos |
| Bedrock (Nova Lite, Titan) | Tokens por pergunta e por ingestão | Não, mas centavos |
| Guardrails | Desligado por padrão | Não; ligue só para testar |
| Budgets | Alerta por e-mail | Sim (2 budgets) |

Preços mudam: confira as páginas oficiais. **Configure `budget_email`** no
`terraform.tfvars` e rode `make tf-destroy` quando terminar uma sessão.

## Pré-requisitos

- `uv`, Terraform >= 1.10 e Docker (Docker Desktop rodando).
- Para a parte AWS: uma conta com credenciais configuradas (de preferência
  `aws configure sso`; o boto3 e o Terraform leem o mesmo perfil via
  `AWS_PROFILE`). Os scripts usam boto3, então o AWS CLI é opcional.
- Acesso aos modelos no Bedrock da região (Nova Lite e Titan Embed v2). Se o
  console pedir para habilitar o modelo, faça isso antes do apply.

## Rodando localmente (grátis)

```bash
make install       # dependências Python
make test          # unitários e de contrato, sem banco
make up            # DynamoDB Local no Docker
make seed-local    # carrega o catálogo fictício
make test-all      # inclui integração com o DynamoDB Local
make invoke ARGS="/case-studies industry=Retail"
make invoke ARGS="/strategic-materials tag=first-call limit=1"
```

O `make invoke` monta exatamente o evento que o Bedrock envia e mostra
exatamente o que o modelo recebe. É onde se depura a Lambda sem gastar token.

## Subindo na AWS

```bash
cp infra/terraform.tfvars.example infra/terraform.tfvars   # ajuste o e-mail
make tf-init
make tf-plan
make tf-apply      # cria tudo e sobe os documentos; o evento do S3 dispara a ingestão
make seed-aws      # carrega o catálogo na tabela
make sync-kb       # opcional: força a ingestão e mostra estatísticas
make retrieve Q="case de varejo"   # testa a KB sem o agente: score e documento
make tools        # lista as tools do Gateway, falando MCP direto (sem agente)
make tool T=docs___search_documents A='{"query":"varejo","asset_type":"case_study"}'
make chat          # conversa com o DRAFT e mostra cada ferramenta chamada
make eval          # golden set: acerto de ferramenta e de parâmetros
make release       # congela o DRAFT atual no alias 'live'
make tf-destroy    # apaga tudo
```

Mudou só a associação da KB? Rode `make prepare` para recompilar o DRAFT.

## Avaliação

[eval/golden.jsonl](eval/golden.jsonl) tem 12 perguntas em português e inglês
com a ferramenta esperada (ou `none` para fora do escopo) e regex para os
parâmetros. O script lê o **trace** do agente, não o texto da resposta, e grava
o resultado em `eval/results/`. Rode antes e depois de cada mudança de prompt,
schema ou modelo e compare. Com `--repeat 3` dá para ver se o agente é estável
na mesma pergunta.

Próximos passos naturais: casos de groundedness para as perguntas da KB e um
juiz validado contra rótulos humanos.

## Estrutura

```
contracts/catalog_api.yaml   contrato OpenAPI que o modelo lê
prompts/                     instrução do agente e descrição da KB
src/catalog_action/          Lambda do action group (sem dependências externas)
src/kb_ingest/               Lambda que dispara a ingestão
src/agent_client/            cliente local: conversa e leitura do trace
scripts/                     seed, invoke local, chat, prepare e sync
eval/                        golden set e avaliação
data/                        catálogo e documentos fictícios
infra/                       Terraform
tests/                       unitários, contrato e integração
```

## Problemas conhecidos

- **macOS com `~/Documents` no iCloud:** o `.pth` do `.venv` pode receber a
  flag `hidden`, e o Python passa a ignorá-lo. Por isso o pytest usa
  `pythonpath = ["src"]` e o Makefile exporta `PYTHONPATH=src`. Fora do
  Makefile, rode `PYTHONPATH=src uv run python ...`.
- **Ingestão concorrente:** se um job já está rodando, a Lambda de ingestão
  ignora o evento. Um arquivo enviado durante o job entra no próximo sync.
  Debounce com SQS resolveria.
- **Busca textual em Python:** o Query lê a partição inteira e filtra na
  Lambda. Serve para centenas de itens. Com milhares, use GSI ou um índice de
  busca.
- **Sem busca híbrida:** o S3 Vectors é só semântico. Nome próprio e sigla
  podem ser mal recuperados; OpenSearch resolveria, com custo mínimo mensal.

## Para evoluir

- Canal Slack: API Gateway, Lambda que responde em menos de 3 segundos e
  enfileira, worker que chama `InvokeAgent` com a thread como `sessionId`.
  Grupo do usuário em `sessionAttributes`, filtrado na Lambda do catálogo.
- Expor o catálogo como ferramenta MCP via AgentCore Gateway, reaproveitável
  por outros agentes.
- State remoto com `use_lockfile` e um segundo ambiente (`environment = "prd"`).
