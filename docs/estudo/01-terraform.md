# Terraform: o que saber sempre, e o que este projeto ensina

## 1. Modelo mental

1. **Declarativo.** Você descreve o estado final; o Terraform calcula os passos.
2. **Três fontes de verdade:** o código, o **state** (o que o Terraform acha que
   criou) e a realidade na AWS. O `plan` compara as três.
3. **O state é o coração.** Ele liga `aws_lambda_function.catalog_action` ao ID
   real. Sem state, o Terraform esquece os recursos e tenta recriá-los. O state
   guarda valores em texto puro, inclusive segredos: é um arquivo sensível.
4. **Grafo de dependências.** Toda referência (`aws_iam_role.agent.arn`) é uma
   aresta. O Terraform ordena e paraleliza por ele.
5. **O provider traduz HCL em chamadas de API** e valida o schema antes. Foi o
   que recusou a descrição da KB com 243 caracteres (limite de 200).

## 2. Checklist de toda vez

| Momento | O que fazer | Por quê |
|---|---|---|
| Antes de tudo | Confirmar conta e região (`aws sts get-caller-identity`) | Aplicar na conta errada é o erro mais caro |
| Mudou provider, módulo ou backend | `terraform init` | Baixa plugins e configura o state |
| Antes de aplicar | `terraform plan` e ler inteiro | Única revisão antes de mexer em recurso real |
| No plan | Procurar `-/+` e "forces replacement" | Destruir e recriar: perda de dados, troca de ID |
| No plan | Conferir "X to add, Y to change, Z to destroy" | Destroy inesperado: pare |
| Mudança feita no console | O próximo apply desfaz | Drift: o código vence |
| Renomear recurso no código | Bloco `moved {}` | Sem ele, destroy e create |
| Recurso criado fora do Terraform | Bloco `import {}` | Passa a ser gerenciado sem recriar |
| Sempre | Versionar `.terraform.lock.hcl`; nunca state nem `.tfvars` com segredo | Reprodutibilidade e segurança |
| Nunca | Editar o state à mão | Use `state mv`, `state rm`, `import` |
| Evitar | `-target` no dia a dia | Deixa o state incoerente; é ferramenta de emergência |

### Sinais do plan

```
+   criar
-   destruir
~   alterar no lugar
-/+ destruir e recriar   <- leia o motivo: "# forces replacement"
<=  ler (data source)
```

### Comandos

| Comando | Para quê |
|---|---|
| `init` | Providers, módulos, backend |
| `fmt -recursive` / `validate` | Formato / sintaxe e schema, sem tocar na AWS |
| `plan` / `plan -out=plan.bin` + `apply plan.bin` | Ver o diff / aplicar exatamente o que foi revisado |
| `output -json` | Valores para scripts |
| `state list` / `state show <addr>` | O que o Terraform gerencia e com quais atributos |
| `console` | Testar expressões e locals |
| `graph` | Ver o grafo de dependências |
| `apply -replace=<addr>` | Forçar recriação de um recurso |
| `destroy` | Apagar tudo do state |

## 3. O que este projeto ensina

### Estrutura (`infra/`)
| Arquivo | Conceito |
|---|---|
| `versions.tf` | `required_version`; provider `~> 6.0` (aceita 6.x, não 7). O lock file fixa a versão exata |
| `variables.tf` | Tipo, default e `validation` (dimensão do embedding falha no plan, não na AWS) |
| `locals.tf` | Valores derivados; `replace` com regex tira o `us.` do inference profile |
| `outputs.tf` | Ponte com os scripts (`terraform output -json`) |
| `providers.tf` | `default_tags` e data sources de identidade da conta |

### Dependências implícitas e explícitas
- **Implícita:** em `lambda_action.tf`, `source_arn = aws_bedrockagent_agent.this[0].agent_arn`.
  Referenciar já ordena.
- **`depends_on`** existe porque o Terraform não enxerga efeito colateral. Três
  casos no projeto, cada um com um motivo:
  1. **KB depende da policy IAM:** a KB só referencia a role; sem a ordem, ela
     pode nascer antes da policy e falhar por permissão.
  2. **Objetos do S3 dependem da notificação:** para o upload disparar a ingestão.
  3. **Action group depende da associação da KB:** o prepare do agente acontece
     ao criar o action group e precisa já ver a KB.

> Regra: todo `depends_on` precisa de um comentário dizendo qual efeito
> invisível está sendo ordenado.

### Repetição e opcionalidade
- **`count` para liga e desliga:** `count = var.enable_auto_ingestion ? 1 : 0`.
  Custo: referenciar com índice (`aws_lambda_function.kb_ingest[0]`).
- **`for_each` para coleções:** `aws_s3_object.docs` sobre `fileset`. Cada
  objeto é identificado pelo nome do arquivo. Com `count`, seria pela posição:
  apagar o primeiro arquivo deslocaria todos e recriaria tudo.
  **`for_each` para coleções, `count` só para liga e desliga.**
- **`dynamic`:** gera um sub-bloco zero ou N vezes (guardrail em `agent.tf`,
  statements opcionais em `iam.tf`, arquivos do zip da Lambda).

### Data sources
- `aws_caller_identity`: ID da conta sem hardcode (o original tinha o ID escrito).
- `aws_iam_policy_document`: policy em HCL, validada e componível, em vez de `jsonencode`.
- `archive_file`: zip da Lambda. `source_code_hash` reimplanta só quando o código
  muda. O mesmo vale para `etag = filemd5(...)` nos documentos.

### Onde o Terraform acaba
- **Alias do agente** congela uma versão ao ser criado. Publicar exige recriar
  (`make release` = `-replace`).
- **Prepare do agente** não roda quando só a associação da KB muda (`make prepare`).
- **Dados do catálogo** ficam fora (`make seed-aws`): dado muda com frequência e
  não é infraestrutura.

Saber dizer "isso não vai no Terraform, e o motivo é este" vale mais que a sintaxe.

### Módulo vs recurso nativo
O original usava o módulo `aws-ia/bedrock`: rápido, mas uma caixa-preta que
exigia um provider OpenSearch dummy. Aqui são recursos nativos: mais linhas, e
cada peça é visível. Regra: módulo para padrão estável e repetido; recurso
nativo quando você precisa entender ou controlar.

## 4. Exercícios

`plan` e `console` só leem: custo zero. O `plan` precisa de credenciais.
Rode tudo dentro de `infra/`.

1. **Console.** `terraform console` e digite `local.base_model_id`,
   `local.foundation_model_arns`, `fileset("../data/docs", "**")`.
2. **Primeiro plan.** `terraform plan`. Conte os recursos. Quais vêm de
   `for_each` (endereço com `["case-studies/..."]`) e quais de `count` (`[0]`)?
3. **Opcional ligado.** `terraform plan -var enable_guardrail=true`. O que entra?
4. **Change vs replacement.** `terraform plan -var chunk_max_tokens=500` e depois
   `terraform plan -var embedding_dimensions=512`. Qual altera no lugar, qual
   recria, e por quê? (Boa pergunta de entrevista.)
5. **Renomear sem destruir.** Troque `aws_dynamodb_table.catalog` por
   `.products`, rode o plan (destroy + create). Adicione
   `moved { from = aws_dynamodb_table.catalog  to = aws_dynamodb_table.products }`
   e rode de novo. Desfaça depois.
6. **Grafo.** `terraform graph | dot -Tpng > graph.png` (precisa do graphviz).

Depois do primeiro apply:

7. **Drift.** Mude a retenção de um log group no console; rode `plan`.
8. **State.** `terraform state list` e `terraform state show aws_bedrockagent_agent.this`.

## 5. Anotações do Lucas

(Respostas dos exercícios e o que surpreendeu. Isso vira material de entrevista.)
