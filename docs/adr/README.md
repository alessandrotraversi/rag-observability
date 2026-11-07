# Architecture Decision Records

Cada ADR registra **uma** decisão: o contexto que a motivou, o que foi decidido, as
alternativas descartadas e as consequências. ADRs são imutáveis depois de aceitos — uma
decisão que muda ganha um novo ADR que *substitui* o anterior.

Base de comparação: o projeto upstream
[`devfullcycle/mba-ia-rag`, branch `observability`](https://github.com/devfullcycle/mba-ia-rag/tree/observability)
(commit `4789051`), referido nos ADRs como **upstream**.

| # | Decisão | Status |
| --- | --- | --- |
| [0001](0001-registrar-decisoes-com-adrs.md) | Registrar decisões arquiteturais com ADRs | Aceito |
| [0002](0002-domain-profile-declarativo.md) | Domínio declarado em um Domain Profile (YAML), fora do código | Aceito |
| [0003](0003-query-plan-gerado-das-facetas.md) | Schema do QueryPlan gerado dinamicamente a partir das facetas | Aceito |
| [0004](0004-portas-e-adapters.md) | Arquitetura de portas e adapters no núcleo do pipeline | Aceito |
| [0005](0005-provedores-de-modelo-agnosticos.md) | Provedores de modelo via `init_chat_model` / `init_embeddings` | Aceito |
| [0006](0006-dsl-de-filtros-canonica.md) | DSL de filtros canônica (estilo Mongo do langchain-postgres) | Aceito |
| [0007](0007-escopo-de-autorizacao-por-requisicao.md) | Escopo de autorização: filtros fixos + escopo por requisição resolvido no servidor | Aceito |
| [0008](0008-convencoes-de-telemetria.md) | Telemetria: namespace `rag.*` e `gen_ai.*` em toda chamada de modelo | Aceito |
| [0009](0009-presets-de-backend-otlp.md) | Backends OTLP como presets; Langfuse deixa de ser caso especial | Aceito |
| [0010](0010-tabela-de-precos-externa.md) | Tabela de preços externa, custo por modelo e fail-fast | Aceito |
| [0011](0011-ledger-de-uso-como-porta.md) | Ledger de uso como porta; orçamento por feature + escopo observado | Aceito |
| [0012](0012-composition-root-sem-singletons.md) | Composition root e injeção de dependências, sem singletons globais | Aceito |
| [0013](0013-vector-store-em-memoria.md) | Vector store em memória com persistência em arquivo | Aceito |
| [0014](0014-erros-tipados.md) | Erros tipados na biblioteca; só as CLIs encerram o processo | Aceito |
| [0015](0015-validacao-de-metadados-na-ingestao.md) | Contrato de metadados validado na ingestão e na subida | Aceito |

Modelo para novos ADRs: [`template.md`](template.md).
