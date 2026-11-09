# 1. Visão geral e arquitetura

## Objetivo

Oferecer um pipeline de RAG **observável** e **governado** que possa ser aplicado a
qualquer base de conhecimento, com qualquer provedor de modelos e qualquer vector store,
trocando configuração — não código.

O ponto de partida é o projeto didático
[`devfullcycle/mba-ia-rag` (branch `observability`)](https://github.com/devfullcycle/mba-ia-rag/tree/observability),
que já resolvia muito bem o *método*: query planning com pedido de esclarecimento,
filtro de metadados eliminatório, reranking, fontes controladas pela aplicação,
OpenTelemetry sem SDK de backend, política de telemetria por ambiente e governança de
custo. O que ele não resolvia era a **generalização**: o domínio (a FCAI), o provedor
(OpenAI) e a infraestrutura (pgvector, arquivo JSONL) estavam no código.

## Metas

- Domínio 100% declarativo (Domain Profile).
- Núcleo sem dependência de provedor, vector store, ledger ou backend de observabilidade.
- Preservar todas as garantias do upstream (ver [03](03-pipeline.md)).
- Rodar e ser testável sem infraestrutura.
- Suportar multi-tenancy real (escopo por requisição).

## Não-metas

- Não é um framework de agentes nem de conversação com memória (cada pergunta é
  independente, como no upstream).
- Não é billing: custos são estimativas.
- Não inclui UI.

## Arquitetura

```mermaid
flowchart LR
  subgraph Entradas
    CLI[cli.chat / cli.retrieve / cli.doctor]
    API[api.create_app]
    ING[ingestion.ingest / ingestion.index]
  end

  subgraph Root[bootstrap.py — composition root]
    direction TB
    S[Settings .env] --> B((build_container))
    P[Domain Profile YAML] --> B
    PR[pricing.yaml] --> B
  end

  subgraph Core[núcleo — sem dependências de infraestrutura]
    PIPE[RagPipeline]
    PROMPTS[PromptSet]
    QP[QueryPlan dinâmico]
    FIL[filters / scope]
    POL[PolicyEngine]
    TEL[Telemetry]
  end

  subgraph Portas
    VI[[VectorIndex]]
    UL[[UsageLedger]]
    SS[[StructuredStep]]
  end

  subgraph Adapters
    PG[(pgvector)]
    MEM[(memory+JSON)]
    JL[(JSONL)]
    LLM[init_chat_model: openai, anthropic, bedrock, ollama…]
    OTLP[OTLP presets: generic, langfuse]
  end

  CLI --> Root
  API --> Root
  Root --> PIPE
  PIPE --> PROMPTS & QP & FIL & POL & TEL
  PIPE --> VI & SS
  POL --> UL
  VI --> PG & MEM
  UL --> JL
  SS --> LLM
  TEL --> OTLP
  ING --> VI
```

## Mapa de módulos

```
rag_observability/
  settings.py              # deployment: provedores, endpoints, limites (env)
  bootstrap.py             # composition root
  api.py                   # FastAPI (create_app, ScopeResolver)
  domain/
    profile.py             # DomainProfile (YAML) + validações
    query_plan.py          # QueryPlan gerado das facetas
  core/
    pipeline.py            # o fluxo: política → plano → busca → rerank → resposta
    prompts.py             # prompts montados do profile
    filters.py             # escopo + facetas → DSL de filtros
    results.py             # resultado, debug, fontes
    ports.py               # VectorIndex, UsageLedger, StructuredStep
    errors.py              # erros tipados
  governance/              # política, preços, ledgers
  observability/           # convenções, presets OTLP, Telemetry
  providers/               # fábricas de modelos e registry de adapters
  vectorstores/            # pgvector, memory
  ingestion/               # loaders, chunking, manifest, ingest, index
  cli/                     # chat, retrieve, doctor
profiles/<nome>/           # profile.yaml + knowledge_base/
config/pricing.yaml
tests/                     # suíte offline com fakes
```
