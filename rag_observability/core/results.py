"""What the pipeline returns. Plain data: callers decide how to present it."""

from typing import Any

from langchain_core.documents import Document
from pydantic import BaseModel, Field

from rag_observability.governance.models import PolicyDecision


class RagAnswer(BaseModel):
    """Structured output of the answer model."""

    answer: str = Field(description="Answer based only on the context.")
    has_answer: bool = Field(description="True only if the context supports the answer.")
    used_chunk_ids: list[str] = Field(
        description="Chunk IDs from the context that support the answer."
    )


class RerankResult(BaseModel):
    """Structured output of the reranker."""

    selected_chunk_ids: list[str] = Field(
        description="Chunk IDs that directly help answer the question, best first. "
        "Empty when no candidate supports the answer."
    )


class Source(BaseModel):
    source_file: str | None = None
    title: str | None = None
    section: str | None = None
    # Profile-declared extra fields (version, url, department, ...).
    attributes: dict[str, Any] = Field(default_factory=dict)


class RetrievalChunkDebug(Source):
    rank: int
    score: float
    chunk_id: str | None = None
    preview: str


class QueryPlanDebug(BaseModel):
    normalized_question: str
    exact_terms: list[str]
    needs_clarification: bool
    clarification_question: str | None = None
    facets: dict[str, list[str]]
    search_query: str
    filters: dict


class PipelineTimings(BaseModel):
    query_planning_ms: float | None = None
    retrieval_ms: float | None = None
    reranking_ms: float | None = None
    answer_generation_ms: float | None = None
    total_ms: float | None = None


class ModelUsage(BaseModel):
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class RagDebug(BaseModel):
    request_id: str
    profile: str
    policy: PolicyDecision | None = None
    query_plan: QueryPlanDebug | None = None  # absent when the policy blocked the run
    retrieved_chunks: list[RetrievalChunkDebug] = Field(default_factory=list)
    selected_chunk_ids: list[str] = Field(default_factory=list)
    timings: PipelineTimings = Field(default_factory=PipelineTimings)
    model_usage: list[ModelUsage] = Field(default_factory=list)
    estimated_cost_usd: float = 0.0


class RagPipelineResult(BaseModel):
    request_id: str
    answer: str
    has_answer: bool
    needs_clarification: bool
    policy_blocked: bool = False
    sources: list[Source]
    debug: RagDebug | None = None


def source_from(document: Document, extra_fields: list[str]) -> Source:
    metadata = document.metadata
    return Source(
        source_file=metadata.get("source_file"),
        title=metadata.get("title"),
        section=metadata.get("section"),
        attributes={f: metadata[f] for f in extra_fields if metadata.get(f) is not None},
    )


def select_documents_by_ids(documents: list[Document], chunk_ids: list[str]) -> list[Document]:
    """Keep only ids that really are among `documents`, in the given order, no dups.

    This is what makes sources trustworthy: an id the model invented is dropped.
    """
    by_id = {d.metadata.get("chunk_id"): d for d in documents}
    selected: list[Document] = []
    for chunk_id in chunk_ids:
        document = by_id.get(chunk_id)
        if document is not None and document not in selected:
            selected.append(document)
    return selected
