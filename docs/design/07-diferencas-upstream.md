# 7. Diferenças em relação ao upstream e guia de migração

Upstream: [`devfullcycle/mba-ia-rag`, branch `observability`](https://github.com/devfullcycle/mba-ia-rag/tree/observability),
commit `4789051`. O histórico git do upstream foi preservado neste repositório; a
refatoração começa no commit seguinte.

## Resumo

| Tema | Upstream | rag-observability | ADR |
| --- | --- | --- | --- |
| Domínio | Constantes em 6 arquivos Python (FCAI) | `profiles/<nome>/profile.yaml` | [0002](../adr/0002-domain-profile-declarativo.md) |
| Schema do plano | `DocType`/`Plan` fixos | `QueryPlan` gerado das facetas | [0003](../adr/0003-query-plan-gerado-das-facetas.md) |
| Arquitetura | Pipeline instancia infraestrutura | Portas + adapters | [0004](../adr/0004-portas-e-adapters.md) |
| Provedor de modelos | OpenAI fixo | Qualquer provedor LangChain | [0005](../adr/0005-provedores-de-modelo-agnosticos.md) |
| Vector store | pgvector fixo | `pgvector`, `memory`, ou caminho pontuado | [0004](../adr/0004-portas-e-adapters.md), [0013](../adr/0013-vector-store-em-memoria.md) |
| Filtros | dict do langchain-postgres | mesma DSL, formalizada como contrato | [0006](../adr/0006-dsl-de-filtros-canonica.md) |
| Autorização | `SAFE_FILTERS` constante, 1 tenant | fixos + escopo por requisição, resolver injetável | [0007](../adr/0007-escopo-de-autorizacao-por-requisicao.md) |
| Spans/atributos | `ai.rag.*` / `app.*`; `gen_ai.*` só na resposta | `rag.*`; `gen_ai.*` em toda chamada de modelo | [0008](../adr/0008-convencoes-de-telemetria.md) |
| Backend OTLP | `if langfuse` no exporter | presets (`generic`, `langfuse`) | [0009](../adr/0009-presets-de-backend-otlp.md) |
| Flush de spans | não (CLI podia perder spans) | `atexit(provider.shutdown)` | [0009](../adr/0009-presets-de-backend-otlp.md) |
| Preços | 1 par fictício no código, para todos os modelos | `config/pricing.yaml` por modelo, fail-fast | [0010](../adr/0010-tabela-de-precos-externa.md) |
| Ledger | arquivo JSONL fixo, chave `tenant` | porta; chave = feature + escopo observado | [0011](../adr/0011-ledger-de-uso-como-porta.md) |
| Configuração | `settings` global na importação | composition root, DI | [0012](../adr/0012-composition-root-sem-singletons.md) |
| Erros | `print` + `SystemExit` na biblioteca | exceções tipadas | [0014](../adr/0014-erros-tipados.md) |
| Contrato de metadados | 2 campos, só na subida | todas as facetas, na ingestão e na subida | [0015](../adr/0015-validacao-de-metadados-na-ingestao.md) |
| Testes | nenhum | suíte offline (28 testes) | — |
| Diagnóstico | `app.main` (conexão + extensão) | `cli.doctor` (settings, política, profile, preços, pacotes, store, contrato) | — |
| Idioma | português no código | `assistant.language` no profile | [0002](../adr/0002-domain-profile-declarativo.md) |

## O que foi mantido sem mudança de comportamento

Query planning com esclarecimento; filtro eliminatório com "na dúvida, sem filtro";
reranking que pode parar o fluxo antes da resposta; fontes cruzadas com o contexto;
chunking por estrutura com cabeçalho de contexto e ids determinísticos; indexação
incremental por hash; política de telemetria por ambiente; conteúdo só como evento em
development; bloqueio de política como resposta controlada (HTTP 200).

## O que foi removido

- `app/chat.py` e `app/context_chat.py` (chat sem RAG e com documento inteiro no
  prompt): eram comparações didáticas do curso, não parte da solução.
- `app/main.py`: substituído por `cli.doctor`.

## Equivalência de arquivos

| Upstream | Aqui |
| --- | --- |
| `app/config.py` | `rag_observability/settings.py` |
| `app/query_planner.py` | `domain/query_plan.py`, `core/filters.py`, `core/prompts.py`, profile `facets`/`planner` |
| `app/rerank.py` | `core/prompts.py` (prompt), `core/results.py` (seleção) |
| `app/rag_pipeline.py` | `core/pipeline.py`, `core/results.py` |
| `app/observability.py` | `observability/tracing.py`, `conventions.py`, `backends.py` |
| `app/governance.py` | `governance/policy.py`, `pricing.py`, `ledgers.py`, `models.py` |
| `app/ingest.py` | `ingestion/loaders.py`, `chunking.py`, `ingest.py` |
| `app/index.py`, `app/manifest.py` | `ingestion/index.py`, `manifest.py`, `vectorstores/pgvector.py` |
| `app/retrieve.py` | `cli/retrieve.py`, `vectorstores/*` |
| `app/rag_chat.py` | `cli/chat.py` |
| `app/api.py` | `api.py` |
| `knowledge_base/` | `profiles/fcai-saas-support/knowledge_base/` |

## Equivalência de variáveis de ambiente

| Upstream | Aqui | Observação |
| --- | --- | --- |
| `OPENAI_API_KEY` | `OPENAI_API_KEY` ou `LLM_API_KEY` | lida pelo próprio provedor |
| `OPENAI_CHAT_MODEL` | `LLM_MODEL` | alias antigo aceito |
| `OPENAI_EMBEDDING_MODEL` | `EMBEDDING_MODEL` | alias antigo aceito |
| — | `LLM_PROVIDER`, `EMBEDDING_PROVIDER` | padrão `openai` |
| — | `RAG_PROFILE`, `RAG_DATA_DIR`, `RAG_FEATURE` | novos |
| — | `VECTOR_STORE` | padrão `pgvector` |
| `DATABASE_URL` | `DATABASE_URL` | igual |
| `OTEL_SERVICE_NAME=fcai-rag-api` | `OTEL_SERVICE_NAME=rag-observability` | só o padrão mudou |
| — | `OTEL_BACKEND` | `auto` reproduz o upstream |
| `AI_*` | `AI_*` | iguais, mais `AI_USAGE_LEDGER`, `AI_PRICING_PATH` |
| — | `API_SCOPE_FROM_HEADERS` | novo |

## Equivalência de telemetria

| Upstream | Aqui |
| --- | --- |
| `ai.rag.pipeline` (e demais `ai.rag.*`) | `rag.pipeline` (e demais `rag.*`) |
| `app.request_id`, `app.feature` | `rag.request_id`, `rag.feature` |
| `app.tenant`, `app.product` | `rag.scope.tenant`, `rag.scope.product` |
| `app.doc_types`, `app.plan` | `rag.query.facet.doc_types`, `rag.query.facet.plan` |
| `app.normalized_question_length`, `app.exact_terms_count` | `rag.query.*` |
| `app.retrieved_chunks_count`, `app.filters` | `rag.retrieval.chunks_count`, `rag.retrieval.filters` |
| `app.selected_chunks_count` | `rag.rerank.selected_count` |
| `app.total_tokens` | `rag.usage.total_tokens` |
| `app.<etapa>_ms` | `rag.duration.<etapa>_ms` |
| `app.policy.*`, `app.budget.*` | `rag.policy.*`, `rag.budget.*` |
| `app.estimated_cost_usd` | `rag.cost.estimated_usd` |
| `app.debug.question` / `answer` | `rag.debug.question` / `answer` |
| `gen_ai.*` só em `answer_generation` | `gen_ai.*` em planning, reranking e answer |

## Migrando um deploy do upstream

1. Mova a base para `profiles/<nome>/knowledge_base/` e escreva o `profile.yaml`
   (o `fcai-saas-support` é o mapeamento direto do código do upstream).
2. Mantenha o `.env`: `OPENAI_*` continuam aceitos. Acrescente `RAG_PROFILE`.
3. Revise `config/pricing.yaml` — o upstream usava preços fictícios.
4. Rode `ingestion.ingest` e `ingestion.index` (o manifest mudou de lugar e de formato:
   haverá um rebuild).
5. Atualize dashboards/filtros do backend de observabilidade para os nomes `rag.*`.
6. O ledger JSONL antigo não é somado no novo esquema; comece um arquivo novo.
