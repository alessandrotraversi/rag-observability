"""Composition root: the only place that knows which adapter goes where.

Settings + profile in, a ready RagPipeline out. Every entry point (CLI, API, your
own application) goes through here instead of importing global singletons.
"""

import logging
import sys
from dataclasses import dataclass

from langchain_core.embeddings import Embeddings

from rag_observability.core.pipeline import ModelSteps, RagPipeline
from rag_observability.core.ports import UsageLedger, VectorIndex
from rag_observability.core.results import RagAnswer, RerankResult
from rag_observability.domain.profile import DomainProfile, load_profile
from rag_observability.domain.query_plan import build_query_plan_model
from rag_observability.governance.ledgers import (
    InMemoryUsageLedger,
    JsonlUsageLedger,
    NullUsageLedger,
)
from rag_observability.governance.policy import PolicyEngine
from rag_observability.governance.pricing import PriceTable, load_price_table
from rag_observability.observability.tracing import Telemetry
from rag_observability.providers.models import build_chat_model, build_embeddings
from rag_observability.providers.registry import resolve
from rag_observability.settings import Settings, load_settings
from rag_observability.vectorstores import BUILTIN_VECTOR_STORES

BUILTIN_LEDGERS = {
    "jsonl": lambda settings: JsonlUsageLedger(settings.usage_ledger_path),
    "memory": lambda settings: InMemoryUsageLedger(),
    "none": lambda settings: NullUsageLedger(),
}


def configure_logging(level: int = logging.INFO) -> None:
    """Run log as JSON lines on stdout; library warnings on stderr."""
    run_log = logging.getLogger("rag_observability.pipeline")
    if not run_log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        run_log.addHandler(handler)
        run_log.setLevel(level)
        run_log.propagate = False
    root = logging.getLogger("rag_observability")
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(handler)
        root.setLevel(logging.WARNING)


def build_embeddings_for(settings: Settings) -> Embeddings:
    return build_embeddings(settings)


def build_index(settings: Settings, profile: DomainProfile, embeddings: Embeddings) -> VectorIndex:
    factory = resolve("vector store", settings.vector_store, BUILTIN_VECTOR_STORES)
    return factory(settings, profile, embeddings)


def build_ledger(settings: Settings) -> UsageLedger:
    factory = resolve("usage ledger", settings.usage_ledger, BUILTIN_LEDGERS)
    return factory(settings)


def build_policy(settings: Settings, prices: PriceTable, ledger: UsageLedger) -> PolicyEngine:
    # An allowed model without a price would cost "zero" and bypass the budget.
    prices.ensure_covers(settings.allowed_models)
    return PolicyEngine(
        allowed_models=settings.allowed_models,
        monthly_budget_usd=settings.ai_monthly_budget_usd,
        max_output_tokens=settings.ai_max_output_tokens,
        ledger=ledger,
        prices=prices,
    )


def build_model_steps(settings: Settings, profile: DomainProfile) -> ModelSteps:
    # temperature defaults to 0: the planner is a classifier and must be stable.
    model = build_chat_model(settings, max_tokens=settings.ai_max_output_tokens)
    return ModelSteps(
        planner=model.with_structured_output(build_query_plan_model(profile)),
        reranker=model.with_structured_output(RerankResult),
        answerer=model.with_structured_output(RagAnswer),
        provider=settings.llm_provider,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.ai_max_output_tokens,
    )


@dataclass
class Container:
    settings: Settings
    profile: DomainProfile
    telemetry: Telemetry
    pipeline: RagPipeline


def build_container(settings: Settings | None = None, *, check_ready: bool = True) -> Container:
    settings = settings or load_settings()
    configure_logging()
    telemetry = Telemetry(settings)  # validates the environment policy first
    telemetry.setup()
    profile = load_profile(settings.profile_path)
    policy = build_policy(settings, load_price_table(settings.pricing_path), build_ledger(settings))
    index = build_index(settings, profile, build_embeddings_for(settings))
    pipeline = RagPipeline(
        profile=profile,
        index=index,
        steps=build_model_steps(settings, profile),
        policy=policy,
        telemetry=telemetry,
        feature=settings.feature_name,
    )
    if check_ready:
        pipeline.check_ready()
    return Container(settings, profile, telemetry, pipeline)
