"""VectorIndex adapter for Postgres + pgvector (langchain-postgres PGVectorStore).

Metadata lives in the `langchain_metadata` JSON column; the filter DSL is evaluated
by langchain-postgres. The table name is the profile's `collection`.
"""

from typing import Any

import psycopg
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from rag_observability.core.errors import ConfigurationError
from rag_observability.domain.profile import DomainProfile
from rag_observability.settings import Settings

ID_COLUMN = {"name": "chunk_id", "data_type": "TEXT", "nullable": False}
METADATA_COLUMN = "langchain_metadata"


class PgVectorIndex:
    def __init__(self, settings: Settings, profile: DomainProfile, embeddings: Embeddings) -> None:
        if not settings.database_url:
            raise ConfigurationError("VECTOR_STORE=pgvector needs DATABASE_URL")
        from langchain_postgres import PGEngine

        self.settings = settings
        self.table = profile.collection
        self.embeddings = embeddings
        self.engine = PGEngine.from_connection_string(url=settings.database_url)
        self._store = None

    # --- connection helpers -----------------------------------------------------
    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.settings.psycopg_dsn)

    def _vector_store(self):
        if self._store is None:
            from langchain_postgres import PGVectorStore

            self._store = PGVectorStore.create_sync(
                engine=self.engine,
                embedding_service=self.embeddings,
                table_name=self.table,
                id_column=ID_COLUMN["name"],
            )
        return self._store

    def enable_extension(self) -> None:
        with self._connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.commit()

    # --- VectorIndex --------------------------------------------------------------
    def exists(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT to_regclass(%s)", (f"public.{self.table}",)).fetchone()
        return row[0] is not None

    def count(self) -> int:
        try:
            with self._connect() as conn:
                return conn.execute(f'SELECT count(*) FROM "{self.table}"').fetchone()[0]
        except psycopg.errors.UndefinedTable:
            return 0

    def reset(self) -> None:
        self.enable_extension()
        # The column size must match the embedding model: probe one vector.
        vector_size = len(self.embeddings.embed_query("dimension probe"))
        self.engine.init_vectorstore_table(
            table_name=self.table,
            vector_size=vector_size,
            id_column=ID_COLUMN,
            overwrite_existing=True,
        )
        self._store = None

    def search(
        self, query: str, k: int, filters: dict[str, Any] | None
    ) -> list[tuple[Document, float]]:
        return self._vector_store().similarity_search_with_score(query, k=k, filter=filters or None)

    def upsert(self, documents: list[Document], ids: list[str]) -> None:
        if documents:
            self._vector_store().add_documents(documents, ids=ids)

    def delete(self, ids: list[str]) -> None:
        if ids:
            self._vector_store().delete(ids=ids)

    def distinct_values(self, field: str) -> set[str]:
        sql = f'SELECT DISTINCT {METADATA_COLUMN}->>%s FROM "{self.table}"'
        with self._connect() as conn:
            rows = conn.execute(sql, (field,)).fetchall()
        return {value for (value,) in rows if value is not None}
