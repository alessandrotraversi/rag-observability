"""Built-in VectorIndex adapters, resolved by name from VECTOR_STORE."""


def _pgvector(settings, profile, embeddings):
    from rag_observability.vectorstores.pgvector import PgVectorIndex

    return PgVectorIndex(settings, profile, embeddings)


def _memory(settings, profile, embeddings):
    from rag_observability.vectorstores.memory import InMemoryIndex

    return InMemoryIndex(settings, profile, embeddings)


BUILTIN_VECTOR_STORES = {"pgvector": _pgvector, "memory": _memory}
