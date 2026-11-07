# 0006. DSL de filtros canônica (estilo Mongo do langchain-postgres)

- **Status:** Aceito
- **Data:** 2026-11-07

## Contexto

Com vector stores plugáveis (ADR 0004), o núcleo precisa expressar filtros sem conhecer o
backend. Cada store tem sua sintaxe (SQL, Qdrant `Filter`, Pinecone, Chroma `where`).

## Decisão

O núcleo produz filtros num único formato — o dicionário estilo Mongo que o
langchain-postgres já entende e que o upstream já usava:

```python
{"tenant": "fcai", "doc_type": {"$in": ["sla", "plan"]}, "plan": {"$in": ["pro", "all"]}}
```

Todo adapter **deve** suportar igualdade implícita e `$in`; `$eq`, `$ne` e `$nin` são
recomendados. O adapter traduz para a sintaxe nativa. O `InMemoryIndex` traz a
implementação de referência (`vectorstores/memory.py: matches`).

## Alternativas consideradas

- **AST própria de filtros** — mais tipada, porém mais código, e afastaria a DSL do que o
  ecossistema LangChain já usa.
- **Deixar o adapter receber o QueryPlan** — vazaria conceitos do domínio para a
  infraestrutura.

## Consequências

- O pgvector funciona sem tradução; outros stores precisam de um tradutor pequeno.
- Os nomes de campo de metadados precisam ser identificadores válidos (o
  langchain-postgres os usa em caminhos JSON), validado no profile.
- Filtros entram nos spans como JSON (`rag.retrieval.filters`), iguais para todo backend.
