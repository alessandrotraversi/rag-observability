"""The policy engine: decides, before any model call, whether a run may happen.

Observability tells what happened; governance decides what is still allowed to
happen. Same semantics as upstream (allowlist, monthly budget, output cap), but the
budget is keyed by feature + observed scope (any fields, not just "tenant"), the
ledger is a port, and cost is computed per model from an external price table.
"""

from datetime import datetime, timezone
from typing import Callable

from rag_observability.core.ports import UsageLedger
from rag_observability.governance.models import (
    ALLOWED_REASON,
    BUDGET_REACHED_REASON,
    MODEL_NOT_ALLOWED_REASON,
    AiPolicy,
    PolicyDecision,
    UsageRecord,
)
from rag_observability.governance.pricing import PriceTable

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PolicyEngine:
    def __init__(
        self,
        allowed_models: list[str],
        monthly_budget_usd: float,
        max_output_tokens: int,
        ledger: UsageLedger,
        prices: PriceTable,
        clock: Clock = utc_now,
    ) -> None:
        self.allowed_models = allowed_models
        self.monthly_budget_usd = monthly_budget_usd
        self.max_output_tokens = max_output_tokens
        self.ledger = ledger
        self.prices = prices
        self.clock = clock

    def policy_for(self, feature: str, scope: dict[str, str]) -> AiPolicy:
        return AiPolicy(
            feature=feature,
            scope=scope,
            allowed_models=self.allowed_models,
            monthly_budget_usd=self.monthly_budget_usd,
            max_output_tokens=self.max_output_tokens,
        )

    def month_start(self) -> datetime:
        now = self.clock()
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def check(self, model: str, feature: str, scope: dict[str, str]) -> PolicyDecision:
        policy = self.policy_for(feature, scope)
        spend = self.ledger.spend_since(self.month_start(), feature, scope)

        if model not in policy.allowed_models:
            allowed, reason = False, MODEL_NOT_ALLOWED_REASON
        elif spend >= policy.monthly_budget_usd:
            allowed, reason = False, BUDGET_REACHED_REASON
        else:
            allowed, reason = True, ALLOWED_REASON

        return PolicyDecision(
            allowed=allowed,
            reason=reason,
            feature=feature,
            scope=scope,
            model=model,
            monthly_budget_usd=policy.monthly_budget_usd,
            current_month_spend_usd=spend,
        )

    def estimate(self, model: str, input_tokens: int, output_tokens: int) -> float:
        return self.prices.estimate(model, input_tokens, output_tokens)

    def record(
        self,
        request_id: str,
        decision: PolicyDecision,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        estimated_cost_usd: float,
    ) -> UsageRecord:
        record = UsageRecord(
            request_id=request_id,
            timestamp=self.clock().isoformat(),
            feature=decision.feature,
            scope=decision.scope,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost_usd,
        )
        self.ledger.record(record)
        return record
