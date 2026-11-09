"""The RAG pipeline: policy -> plan -> retrieve -> rerank -> answer -> sources.

Same flow and the same guarantees as upstream (app/rag_pipeline.py):
- the policy is decided before anything touches a model;
- an ambiguous question returns a clarification instead of a guess;
- no chunk / no relevant chunk stops the run *without* calling the answer model;
- sources come from the application, never from the model.

What changed is how it is built: every collaborator is injected (profile, index,
model steps, policy engine, telemetry), so the same class serves any domain, any
provider and any vector store, and can be tested without network (docs/adr/0012).
"""

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator
from uuid import uuid4

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.documents import Document
from langchain_core.prompt_values import PromptValue

from rag_observability.core.errors import IndexContractError, IndexNotReadyError
from rag_observability.core.filters import build_filters, resolve_scope
from rag_observability.core.ports import StructuredStep, VectorIndex
from rag_observability.core.prompts import PromptSet
from rag_observability.core.results import (
    ModelUsage,
    PipelineTimings,
    QueryPlanDebug,
    RagDebug,
    RagPipelineResult,
    RetrievalChunkDebug,
    select_documents_by_ids,
    source_from,
)
from rag_observability.domain.profile import DomainProfile
from rag_observability.domain.query_plan import (
    BaseQueryPlan,
    build_search_query,
    facet_selections,
)
from rag_observability.governance.models import PolicyDecision
from rag_observability.governance.policy import PolicyEngine
from rag_observability.observability import conventions as conv
from rag_observability.observability.tracing import Telemetry

PromptCallback = Callable[[str, PromptValue], None]

# One JSON line per run: counts, timings, ids and file names — never prompts,
# chunks, answers or credentials.
run_log = logging.getLogger("rag_observability.pipeline")


@dataclass
class ModelSteps:
    """The three structured model calls, already bound to their output schemas."""

    planner: StructuredStep
    reranker: StructuredStep
    answerer: StructuredStep
    provider: str
    model: str
    temperature: float | None = None
    max_tokens: int | None = None


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


class RagPipeline:
    def __init__(
        self,
        *,
        profile: DomainProfile,
        index: VectorIndex,
        steps: ModelSteps,
        policy: PolicyEngine,
        telemetry: Telemetry,
        feature: str = "rag_chat",
    ) -> None:
        self.profile = profile
        self.index = index
        self.steps = steps
        self.policy = policy
        self.telemetry = telemetry
        self.feature = feature
        self.prompts = PromptSet(profile)

    # --- startup checks -----------------------------------------------------------
    def check_ready(self) -> None:
        if not self.index.count():
            raise IndexNotReadyError(
                f"collection '{self.profile.collection}' is missing or empty. "
                "Run 'python -m rag_observability.ingestion.ingest' and then "
                "'python -m rag_observability.ingestion.index' first."
            )
        self.check_index_contract()

    def check_index_contract(self) -> None:
        """Every facet value in the index must be one the planner can produce.

        Otherwise its documents silently vanish from every filtered search. Upstream
        checked two hardcoded literals; here every facet of the profile is checked.
        """
        problems = []
        for facet in self.profile.facets:
            indexed = self.index.distinct_values(facet.metadata_field)
            unknown = indexed - set(facet.values) - ({facet.wildcard} if facet.wildcard else set())
            if unknown:
                problems.append(f"{facet.metadata_field}: {', '.join(sorted(unknown))}")
        if problems:
            raise IndexContractError(
                "the index has metadata values the profile's facets do not declare ("
                + "; ".join(problems)
                + "). Add them to the facet values in the profile."
            )

    # --- run ----------------------------------------------------------------------
    def run(
        self,
        question: str,
        *,
        scope: dict[str, Any] | None = None,
        use_rerank: bool = True,
        include_debug: bool = False,
        on_prompt: PromptCallback | None = None,
    ) -> RagPipelineResult:
        request_id = str(uuid4())
        timings = PipelineTimings()
        usage = UsageMetadataCallbackHandler()
        resolved_scope = resolve_scope(self.profile, scope)
        observed_scope = {
            f: str(resolved_scope[f])
            for f in self.profile.observed_scope_fields
            if f in resolved_scope
        }

        # Decided before anything runs: a blocked request never reaches a model.
        decision = self.policy.check(self.steps.model, self.feature, observed_scope)

        try:
            with self._step(timings, "total_ms", conv.PIPELINE_SPAN) as span:
                self.telemetry.set_attributes(
                    span,
                    {
                        conv.REQUEST_ID: request_id,
                        conv.PROFILE: self.profile.name,
                        conv.FEATURE: self.feature,
                        conv.USE_RERANK: use_rerank,
                        conv.POLICY_ALLOWED: decision.allowed,
                        conv.POLICY_REASON: decision.reason,
                        conv.MONTHLY_BUDGET_USD: decision.monthly_budget_usd,
                        conv.CURRENT_SPEND_USD: decision.current_month_spend_usd,
                        **{conv.scope_attribute(k): v for k, v in observed_scope.items()},
                    },
                )
                self.telemetry.record_debug_content(span, question=question)

                debug = RagDebug(
                    request_id=request_id, profile=self.profile.name,
                    policy=decision, timings=timings,
                )
                if decision.allowed:
                    result = self._execute(
                        question, resolved_scope, use_rerank, debug, usage, on_prompt
                    )
                else:
                    result = self._finish(debug, self.profile.messages.policy_blocked, policy_blocked=True)

                debug.model_usage = self._model_usage(usage.usage_metadata)
                debug.estimated_cost_usd = round(
                    sum(u.estimated_cost_usd for u in debug.model_usage), 6
                )
                self.telemetry.set_attributes(
                    span,
                    {
                        conv.HAS_ANSWER: result.has_answer,
                        conv.NEEDS_CLARIFICATION: result.needs_clarification,
                        conv.SOURCES_COUNT: len(result.sources),
                        conv.TOTAL_TOKENS: sum(u.total_tokens for u in debug.model_usage),
                        conv.ESTIMATED_COST_USD: debug.estimated_cost_usd,
                    },
                )
                # Also when it is a clarification question or a refusal.
                self.telemetry.record_debug_content(span, answer=result.answer)
        except Exception as exc:
            self._log_run(
                {
                    "request_id": request_id,
                    "profile": self.profile.name,
                    "used_rerank": use_rerank,
                    "timings": timings.model_dump(),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
            raise

        # Only a run that really called a model enters the ledger.
        for entry in debug.model_usage:
            self.policy.record(
                request_id, decision, self.steps.provider, entry.model,
                entry.input_tokens, entry.output_tokens, entry.total_tokens,
                entry.estimated_cost_usd,
            )

        self._log_run(self._run_record(result, debug, decision, use_rerank))
        if not include_debug:
            result.debug = None
        return result

    # --- steps --------------------------------------------------------------------
    def _execute(
        self,
        question: str,
        scope: dict[str, Any],
        use_rerank: bool,
        debug: RagDebug,
        usage: UsageMetadataCallbackHandler,
        on_prompt: PromptCallback | None,
    ) -> RagPipelineResult:
        timings = debug.timings

        planner_prompt = self.prompts.planner_prompt(question)
        if on_prompt:
            on_prompt("Query planner prompt", planner_prompt)
        with self._step(timings, "query_planning_ms", conv.QUERY_PLANNING_SPAN) as span:
            plan: BaseQueryPlan = self._invoke_model(
                span, self.steps.planner, planner_prompt, usage
            )
            selections = facet_selections(plan, self.profile)
            self.telemetry.set_attributes(
                span,
                {
                    conv.NORMALIZED_QUESTION_LENGTH: len(plan.normalized_question),
                    conv.EXACT_TERMS_COUNT: len(plan.exact_terms),
                    conv.NEEDS_CLARIFICATION: plan.needs_clarification,
                    **{conv.facet_attribute(k): v for k, v in selections.items() if v},
                },
            )

        filters = build_filters(self.profile, scope, selections)
        debug.query_plan = QueryPlanDebug(
            normalized_question=plan.normalized_question,
            exact_terms=plan.exact_terms,
            needs_clarification=plan.needs_clarification,
            clarification_question=plan.clarification_question,
            facets=selections,
            search_query=build_search_query(plan),
            filters=filters,
        )

        if plan.needs_clarification:
            answer = plan.clarification_question or self.profile.messages.clarification_fallback
            return self._finish(debug, answer, needs_clarification=True)

        top_k = self.profile.retrieval.top_k
        with self._step(timings, "retrieval_ms", conv.RETRIEVAL_SPAN) as span:
            results = self.index.search(build_search_query(plan), k=top_k, filters=filters)
            self.telemetry.set_attributes(
                span,
                {conv.RETRIEVED_CHUNKS_COUNT: len(results), conv.FILTERS: filters, conv.TOP_K: top_k},
            )
        debug.retrieved_chunks = self._retrieval_debug(results)
        if not results:
            return self._finish(debug, self.profile.messages.no_answer)

        top_n = self.profile.retrieval.rerank_top_n
        if use_rerank:
            rerank_prompt = self.prompts.rerank_prompt(results, question, plan)
            if on_prompt:
                on_prompt("Reranker prompt", rerank_prompt)
            with self._step(timings, "reranking_ms", conv.RERANKING_SPAN) as span:
                reranked = self._invoke_model(span, self.steps.reranker, rerank_prompt, usage)
                documents = select_documents_by_ids(
                    [d for d, _ in results], reranked.selected_chunk_ids
                )[:top_n]
                self.telemetry.set_attributes(span, {conv.SELECTED_CHUNKS_COUNT: len(documents)})
        else:
            documents = [d for d, _ in results[:top_n]]

        debug.selected_chunk_ids = [d.metadata.get("chunk_id") for d in documents]
        if not documents:
            return self._finish(debug, self.profile.messages.no_answer)

        answer_prompt = self.prompts.answer_prompt(documents, question)
        if on_prompt:
            on_prompt("Final answer prompt", answer_prompt)
        with self._step(timings, "answer_generation_ms", conv.ANSWER_GENERATION_SPAN) as span:
            response = self._invoke_model(span, self.steps.answerer, answer_prompt, usage)
            self.telemetry.set_attributes(span, {conv.HAS_ANSWER: response.has_answer})

        sources = (
            [
                source_from(d, self.profile.sources.extra_fields)
                for d in select_documents_by_ids(documents, response.used_chunk_ids)
            ]
            if response.has_answer
            else []
        )
        return RagPipelineResult(
            request_id=debug.request_id,
            answer=response.answer,
            has_answer=response.has_answer,
            needs_clarification=False,
            sources=sources,
            debug=debug,
        )

    def _invoke_model(
        self, span, step: StructuredStep, prompt: PromptValue, usage: UsageMetadataCallbackHandler
    ):
        """Call a model step and describe it with the GenAI semantic conventions.

        A second handler scoped to this call gives per-step tokens; the shared one
        accumulates the whole run for the cost and the ledger.
        """
        step_usage = UsageMetadataCallbackHandler()
        response = step.invoke(prompt, config={"callbacks": [usage, step_usage]})
        attributes = {
            conv.OPERATION_NAME: conv.CHAT_OPERATION,
            conv.PROVIDER_NAME: self.steps.provider,
            conv.REQUEST_MODEL: self.steps.model,
            conv.REQUEST_TEMPERATURE: self.steps.temperature,
            conv.REQUEST_MAX_TOKENS: self.steps.max_tokens,
        }
        for model, counters in step_usage.usage_metadata.items():
            attributes.update(
                {
                    conv.RESPONSE_MODEL: model,
                    conv.INPUT_TOKENS: counters.get("input_tokens", 0),
                    conv.OUTPUT_TOKENS: counters.get("output_tokens", 0),
                    conv.TOTAL_TOKENS: counters.get("total_tokens", 0),
                }
            )
        self.telemetry.set_attributes(span, attributes)
        return response

    # --- helpers ------------------------------------------------------------------
    @contextmanager
    def _step(self, timings: PipelineTimings, field: str, span_name: str) -> Iterator[Any]:
        started = time.perf_counter()
        with self.telemetry.span(span_name) as span:
            try:
                yield span
            finally:
                elapsed = _elapsed_ms(started)
                setattr(timings, field, elapsed)
                self.telemetry.set_attributes(span, {conv.duration_attribute(field): elapsed})

    def _finish(
        self, debug: RagDebug, answer: str, *, needs_clarification: bool = False,
        policy_blocked: bool = False,
    ) -> RagPipelineResult:
        return RagPipelineResult(
            request_id=debug.request_id,
            answer=answer,
            has_answer=False,
            needs_clarification=needs_clarification,
            policy_blocked=policy_blocked,
            sources=[],
            debug=debug,
        )

    def _retrieval_debug(self, results: list[tuple[Document, float]]) -> list[RetrievalChunkDebug]:
        limit = self.profile.retrieval.preview_chars
        extra = self.profile.sources.extra_fields
        return [
            RetrievalChunkDebug(
                **source_from(document, extra).model_dump(),
                rank=rank,
                score=score,
                chunk_id=document.metadata.get("chunk_id"),
                preview=document.page_content[:limit],
            )
            for rank, (document, score) in enumerate(results, start=1)
        ]

    def _model_usage(self, usage_metadata: dict) -> list[ModelUsage]:
        entries = []
        for model, counters in usage_metadata.items():
            input_tokens = counters.get("input_tokens", 0)
            output_tokens = counters.get("output_tokens", 0)
            entries.append(
                ModelUsage(
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=counters.get("total_tokens", input_tokens + output_tokens),
                    estimated_cost_usd=self.policy.estimate(model, input_tokens, output_tokens),
                )
            )
        return entries

    def _run_record(
        self, result: RagPipelineResult, debug: RagDebug, decision: PolicyDecision, use_rerank: bool
    ) -> dict:
        return {
            "request_id": debug.request_id,
            "profile": self.profile.name,
            "feature": self.feature,
            "scope": decision.scope,
            "has_answer": result.has_answer,
            "needs_clarification": result.needs_clarification,
            "used_rerank": use_rerank,
            "policy_allowed": decision.allowed,
            "policy_reason": decision.reason,
            "monthly_budget_usd": decision.monthly_budget_usd,
            "current_month_spend_usd": decision.current_month_spend_usd,
            "estimated_cost_usd": debug.estimated_cost_usd,
            "retrieved_chunks_count": len(debug.retrieved_chunks),
            "selected_chunks_count": len(debug.selected_chunk_ids),
            "source_files": [s.source_file for s in result.sources],
            "timings": debug.timings.model_dump(),
            "model_usage": [u.model_dump() for u in debug.model_usage],
        }

    @staticmethod
    def _log_run(record: dict) -> None:
        run_log.info(json.dumps(record, ensure_ascii=False, default=str))
