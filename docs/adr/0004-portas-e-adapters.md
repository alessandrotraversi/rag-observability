# 0004. Arquitetura de portas e adapters no núcleo do pipeline

- **Status:** Aceito
- **Data:** 2026-11-07

## Contexto

O pipeline do upstream instancia diretamente `PGVectorStore`, `OpenAIEmbeddings`,
`init_chat_model(model_provider="openai")` e escreve o ledger num arquivo. Trocar
qualquer peça (Qdrant, Bedrock, Redis) significava editar o pipeline, e testá-lo exigia
Postgres e uma chave da OpenAI.

## Decisão

O núcleo (`rag_observability/core`) depende apenas de **portas** — `Protocol`s em
`core/ports.py`:

| Porta | Responsabilidade | Adapters incluídos |
| --- | --- | --- |
| `VectorIndex` | `count`, `exists`, `reset`, `search`, `upsert`, `delete`, `distinct_values` | `PgVectorIndex`, `InMemoryIndex` |
| `UsageLedger` | `record`, `spend_since` | `JsonlUsageLedger`, `InMemoryUsageLedger`, `NullUsageLedger` |
| `StructuredStep` | `invoke(prompt, config)` com saída estruturada | qualquer `BaseChatModel.with_structured_output(...)` |
| Loader (função) | arquivos → `SourceDocument` | `markdown` |

Adapters são escolhidos por nome nas settings (`VECTOR_STORE`, `AI_USAGE_LEDGER`,
`ingestion.loader`) ou por caminho pontuado `pacote.modulo:Fabrica`, sem tocar no núcleo
(`providers/registry.py`).

## Alternativas consideradas

- **Usar `langchain_core.vectorstores.VectorStore` como porta** — não expõe `count`,
  `exists`, `reset` nem `distinct_values`, de que o pipeline precisa para a checagem de
  contrato e a indexação incremental; e o comportamento de filtros varia por integração.
- **Plugins via entry points** — mais cerimônia; o caminho pontuado resolve o mesmo caso.

## Consequências

- O pipeline roda inteiro offline em testes com fakes (`tests/conftest.py`).
- Um novo vector store é uma classe com sete métodos; precisa implementar a DSL de
  filtros (ADR 0006).
- A porta `VectorIndex` é deliberadamente mínima: recursos específicos (busca híbrida,
  MMR) ficam dentro do adapter.
