"""VectorIndex adapter kept in memory and persisted to a JSON file.

Zero infrastructure: good for a first run, demos, CI and tests. Exact (brute-force)
cosine search, so it is meant for small corpora (thousands of chunks), not
production (docs/adr/0013). Scores are cosine *distances* (lower is closer), the
same convention pgvector uses.
"""

import json
import math
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from rag_observability.domain.profile import DomainProfile
from rag_observability.settings import Settings


def matches(metadata: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    """Evaluate the canonical filter DSL: equality, $eq, $ne, $in, $nin."""
    for field, condition in (filters or {}).items():
        value = metadata.get(field)
        if isinstance(condition, dict):
            (operator, expected), = condition.items()
            if operator == "$eq" and value != expected:
                return False
            if operator == "$ne" and value == expected:
                return False
            if operator == "$in" and value not in expected:
                return False
            if operator == "$nin" and value in expected:
                return False
            if operator not in {"$eq", "$ne", "$in", "$nin"}:
                raise ValueError(f"unsupported filter operator for memory index: {operator}")
        elif value != condition:
            return False
    return True


def cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return 1.0 - (dot / norm if norm else 0.0)


class InMemoryIndex:
    def __init__(
        self,
        settings: Settings | None,
        profile: DomainProfile,
        embeddings: Embeddings,
        path: Path | None = None,
    ) -> None:
        self.embeddings = embeddings
        if path is None and settings is not None:
            path = settings.data_dir / profile.collection / "memory_index.json"
        self.path = path
        self.records: dict[str, dict[str, Any]] = {}
        self._exists = False
        if self.path and self.path.exists():
            self.records = json.loads(self.path.read_text(encoding="utf-8"))
            self._exists = True

    def _save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.records, ensure_ascii=False), encoding="utf-8")

    def exists(self) -> bool:
        return self._exists

    def count(self) -> int:
        return len(self.records)

    def reset(self) -> None:
        self.records = {}
        self._exists = True
        self._save()

    def search(
        self, query: str, k: int, filters: dict[str, Any] | None
    ) -> list[tuple[Document, float]]:
        vector = self.embeddings.embed_query(query)
        scored = [
            (cosine_distance(vector, record["embedding"]), chunk_id)
            for chunk_id, record in self.records.items()
            if matches(record["metadata"], filters)
        ]
        scored.sort()
        return [
            (
                Document(
                    page_content=self.records[chunk_id]["content"],
                    metadata=self.records[chunk_id]["metadata"],
                ),
                round(score, 6),
            )
            for score, chunk_id in scored[:k]
        ]

    def upsert(self, documents: list[Document], ids: list[str]) -> None:
        if not documents:
            return
        vectors = self.embeddings.embed_documents([d.page_content for d in documents])
        for chunk_id, document, vector in zip(ids, documents, vectors):
            self.records[chunk_id] = {
                "content": document.page_content,
                "metadata": document.metadata,
                "embedding": vector,
            }
        self._exists = True
        self._save()

    def delete(self, ids: list[str]) -> None:
        for chunk_id in ids:
            self.records.pop(chunk_id, None)
        self._save()

    def distinct_values(self, field: str) -> set[str]:
        return {
            str(r["metadata"][field])
            for r in self.records.values()
            if r["metadata"].get(field) is not None
        }
