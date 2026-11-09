"""Telemetry vocabulary: every span and attribute name, spelled out once.

Two namespaces (docs/adr/0008):
- gen_ai.*  OpenTelemetry GenAI semantic conventions, on EVERY model call
            (planner, reranker and answer), so backends classify each as a generation.
- rag.*     What is specific to this pipeline. Upstream used "app.*"; "rag.*" names
            the concern instead of the application, so several apps can share one
            backend and the same dashboards.
"""

# Spans: one root plus one per step.
PIPELINE_SPAN = "rag.pipeline"
QUERY_PLANNING_SPAN = "rag.query_planning"
RETRIEVAL_SPAN = "rag.retrieval"
RERANKING_SPAN = "rag.reranking"
ANSWER_GENERATION_SPAN = "rag.answer_generation"

# Root span.
REQUEST_ID = "rag.request_id"
PROFILE = "rag.profile"
FEATURE = "rag.feature"
USE_RERANK = "rag.use_rerank"
HAS_ANSWER = "rag.has_answer"
NEEDS_CLARIFICATION = "rag.needs_clarification"
SOURCES_COUNT = "rag.sources_count"
TOTAL_TOKENS = "rag.usage.total_tokens"


def scope_attribute(field: str) -> str:
    """Authorization scope values (tenant, product, ...), as the profile observes them."""
    return f"rag.scope.{field}"


def facet_attribute(facet: str) -> str:
    """What the planner selected on a facet."""
    return f"rag.query.facet.{facet}"


def duration_attribute(step: str) -> str:
    """Step duration in ms, named after the PipelineTimings field it fills."""
    return f"rag.duration.{step}"


# Query planning.
NORMALIZED_QUESTION_LENGTH = "rag.query.normalized_question_length"
EXACT_TERMS_COUNT = "rag.query.exact_terms_count"

# Retrieval / reranking.
RETRIEVED_CHUNKS_COUNT = "rag.retrieval.chunks_count"
FILTERS = "rag.retrieval.filters"
TOP_K = "rag.retrieval.top_k"
SELECTED_CHUNKS_COUNT = "rag.rerank.selected_count"

# Governance.
POLICY_ALLOWED = "rag.policy.allowed"
POLICY_REASON = "rag.policy.reason"
MONTHLY_BUDGET_USD = "rag.budget.monthly_usd"
CURRENT_SPEND_USD = "rag.budget.current_spend_usd"
ESTIMATED_COST_USD = "rag.cost.estimated_usd"

# Debug content events (development only).
DEBUG_QUESTION_EVENT = "rag.debug.question"
DEBUG_ANSWER_EVENT = "rag.debug.answer"

# GenAI semantic conventions.
OPERATION_NAME = "gen_ai.operation.name"
PROVIDER_NAME = "gen_ai.provider.name"
REQUEST_MODEL = "gen_ai.request.model"
RESPONSE_MODEL = "gen_ai.response.model"
INPUT_TOKENS = "gen_ai.usage.input_tokens"
OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
REQUEST_TEMPERATURE = "gen_ai.request.temperature"
CHAT_OPERATION = "chat"
