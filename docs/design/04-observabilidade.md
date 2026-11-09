# 4. Observabilidade

## Princípios (mantidos do upstream)

- A aplicação fala **só OpenTelemetry**; o backend é decisão de deploy.
- `OBSERVABILITY_ENABLED=false` → nenhum provider configurado, spans viram no-op.
- Atributos só seguros: ids, contagens, flags, filtros, tempos, modelo, tokens, custo.
- Pergunta e resposta: apenas como **eventos** de debug, apenas em development, apenas
  com `OBSERVABILITY_CAPTURE_CONTENT=true`.
- Nunca saem: prompts, contexto, conteúdo de chunks, documentos, credenciais, valores de
  headers OTLP.

## Spans

| Span | Atributos |
| --- | --- |
| `rag.pipeline` | `rag.request_id`, `rag.profile`, `rag.feature`, `rag.use_rerank`, `rag.scope.<campo>`, `rag.policy.allowed`, `rag.policy.reason`, `rag.budget.monthly_usd`, `rag.budget.current_spend_usd`, `rag.has_answer`, `rag.needs_clarification`, `rag.sources_count`, `rag.usage.total_tokens`, `rag.cost.estimated_usd`, `rag.duration.total_ms` |
| `rag.query_planning` | `gen_ai.*`, `rag.query.normalized_question_length`, `rag.query.exact_terms_count`, `rag.query.facet.<faceta>`, `rag.needs_clarification`, `rag.duration.query_planning_ms` |
| `rag.retrieval` | `rag.retrieval.chunks_count`, `rag.retrieval.filters`, `rag.retrieval.top_k`, `rag.duration.retrieval_ms` |
| `rag.reranking` | `gen_ai.*`, `rag.rerank.selected_count`, `rag.duration.reranking_ms` |
| `rag.answer_generation` | `gen_ai.*`, `rag.has_answer`, `rag.duration.answer_generation_ms` |

`gen_ai.*` = `gen_ai.operation.name=chat`, `gen_ai.provider.name`,
`gen_ai.request.model`, `gen_ai.request.temperature`, `gen_ai.request.max_tokens`,
`gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`,
`rag.usage.total_tokens` — **por etapa**.

Resource: `service.name`, `service.version`, `deployment.environment.name`.
Erro: status `ERROR` com `Tipo: mensagem` e `error.type`, sem stack trace.

## Política por ambiente

| | development | staging | production |
| --- | --- | --- | --- |
| Sample rate | sempre 1.0 | `OBSERVABILITY_SAMPLE_RATE` | `OBSERVABILITY_SAMPLE_RATE` |
| `OBSERVABILITY_CAPTURE_CONTENT=true` | permitido | **recusa subir** | **recusa subir** |

Sampler `ParentBased(TraceIdRatioBased)`: ou o trace inteiro é gravado, ou nada.

## Destinos

| `OTEL_TRACES_EXPORTER` | `OTEL_BACKEND` | Resultado |
| --- | --- | --- |
| `console` | — | spans impressos ao terminar (desenvolvimento) |
| `otlp` | `generic` | `OTEL_EXPORTER_OTLP_ENDPOINT` + `OTEL_EXPORTER_OTLP_HEADERS` (Jaeger, Collector, Phoenix, Datadog, …) |
| `otlp` | `langfuse` | `LANGFUSE_HOST/api/public/otel`, `Authorization: Basic`, `x-langfuse-ingestion-version: 4` |
| `otlp` | `auto` | `langfuse` se as chaves existem, senão `generic` |

O `docker-compose.yml` mantém os profiles `jaeger` (1 container) e `observability`
(Langfuse completo), com nomes genéricos.

## Log estruturado

Uma linha JSON por execução em stdout (`rag_observability.pipeline`): `request_id`,
`profile`, `feature`, `scope`, flags, decisão de política, custo, contagens, arquivos de
fonte, tempos, uso por modelo. Em erro: tipo e mensagem. Nunca conteúdo.
