"""Ports: the contracts the core depends on. Adapters live elsewhere.

The pipeline never imports a vector store, a ledger backend or a model SDK. It
receives objects that satisfy these protocols (see docs/adr/0004).
"""

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from langchain_core.documents import Document

from rag_observability.governance.models import UsageRecord


@runtime_checkable
class VectorIndex(Protocol):
    """A collection of embedded chunks addressable by chunk id."""

    def count(self) -> int:
        """Number of chunks; 0 when the collection does not exist."""

    def exists(self) -> bool: ...

    def reset(self) -> None:
        """Drop and recreate the collection, empty."""

    def search(
        self, query: str, k: int, filters: dict[str, Any] | None
    ) -> list[tuple[Document, float]]:
        """Similarity search. Score is a distance: lower is closer."""

    def upsert(self, documents: list[Document], ids: list[str]) -> None: ...

    def delete(self, ids: list[str]) -> None: ...

    def distinct_values(self, field: str) -> set[str]:
        """Distinct non-null values of a metadata field across the collection."""


@runtime_checkable
class UsageLedger(Protocol):
    """Where estimated usage is recorded and read back for the budget."""

    def record(self, record: UsageRecord) -> None: ...

    def spend_since(self, since: datetime, feature: str, scope: dict[str, str]) -> float:
        """Total estimated cost of records at/after `since` matching feature and scope."""


@runtime_checkable
class StructuredStep(Protocol):
    """A model call with structured output (what with_structured_output returns)."""

    def invoke(self, input: Any, config: dict | None = None) -> Any: ...
