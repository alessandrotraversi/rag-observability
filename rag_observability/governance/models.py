"""Governance data: the policy, its decision and one line of the usage ledger."""

from pydantic import BaseModel, Field

ALLOWED_REASON = "within policy"
MODEL_NOT_ALLOWED_REASON = "model not allowed"
BUDGET_REACHED_REASON = "monthly budget reached"


class AiPolicy(BaseModel):
    feature: str
    scope: dict[str, str] = Field(default_factory=dict)
    allowed_models: list[str]
    monthly_budget_usd: float
    max_output_tokens: int


class PolicyDecision(BaseModel):
    allowed: bool
    reason: str
    feature: str
    scope: dict[str, str] = Field(default_factory=dict)
    model: str
    monthly_budget_usd: float
    current_month_spend_usd: float


class UsageRecord(BaseModel):
    request_id: str
    timestamp: str
    feature: str
    scope: dict[str, str] = Field(default_factory=dict)
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
