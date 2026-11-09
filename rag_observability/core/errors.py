"""Typed errors. Library code raises; only the CLIs decide to print and exit."""


class RagError(Exception):
    """Base class for every error raised by rag_observability."""


class ConfigurationError(RagError):
    """Settings, profile or pricing do not hold together."""


class IndexNotReadyError(RagError):
    """The collection is missing or empty: run ingest and index first."""


class IndexContractError(RagError):
    """The index holds metadata values the profile's facets do not declare."""


class IngestionError(RagError):
    """A source document is missing, empty or lacks required metadata."""


class IndexingError(RagError):
    """The chunks file is missing or malformed."""


class ScopeError(RagError):
    """The request scope is missing, not allowed, or tries to override an enforced filter."""
