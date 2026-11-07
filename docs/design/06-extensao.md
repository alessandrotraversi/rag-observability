# 6. Pontos de extensão

Tudo abaixo se pluga **sem editar o núcleo**.

## Novo domínio

Um diretório em `profiles/` — ver [02](02-domain-profile.md).

## Novo provedor de modelo

Instale o pacote de integração LangChain e configure:

```bash
pip install langchain-anthropic
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
ANTHROPIC_API_KEY=...
AI_ALLOWED_MODELS=claude-sonnet-4-5   # e um preço em config/pricing.yaml
```

Exemplos de embeddings: `EMBEDDING_PROVIDER=ollama EMBEDDING_MODEL=nomic-embed-text`,
`EMBEDDING_PROVIDER=bedrock`, `EMBEDDING_PROVIDER=google_genai`. O modelo de chat precisa
suportar structured output.

## Novo vector store

```python
# meu_pacote/qdrant_index.py
class QdrantIndex:
    def __init__(self, settings, profile, embeddings): ...
    def count(self) -> int: ...
    def exists(self) -> bool: ...
    def reset(self) -> None: ...
    def search(self, query, k, filters): ...      # traduz a DSL (ADR 0006)
    def upsert(self, documents, ids): ...
    def delete(self, ids): ...
    def distinct_values(self, field) -> set[str]: ...
```

```bash
VECTOR_STORE=meu_pacote.qdrant_index:QdrantIndex
```

Score deve ser **distância** (menor = mais próximo). Use os testes de
`tests/test_governance_and_ingestion.py::test_memory_filter_dsl` como referência.

## Novo ledger

```python
class PostgresLedger:
    def __init__(self, settings): ...
    def record(self, record: UsageRecord) -> None: ...
    def spend_since(self, since, feature, scope) -> float: ...
```

```bash
AI_USAGE_LEDGER=meu_pacote.ledger:PostgresLedger
```

## Novo loader

```python
def load_confluence(profile) -> list[SourceDocument]: ...
```

```yaml
ingestion:
  loader: meu_pacote.loaders:load_confluence
```

## Novo backend OTLP

Acrescente uma função `Settings → (endpoint, headers)` em
`observability/backends.py: PRESETS` e um valor em `OTEL_BACKEND`.

## Escopo a partir da sua autenticação

```python
from rag_observability.api import create_app

def scope_from_jwt(request):
    claims = verify(request.headers["authorization"])
    return {"tenant": claims["org_id"]}

app = create_app(scope_resolver=scope_from_jwt)
```

## Embutir o pipeline

```python
from rag_observability.bootstrap import build_container
from rag_observability.settings import load_settings

container = build_container(load_settings(RAG_PROFILE="profiles/hr-handbook/profile.yaml"))
result = container.pipeline.run("How many vacation days in Portugal?", scope={"company": "acme-labs"})
```
