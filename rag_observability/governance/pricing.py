"""Price table, loaded from YAML (config/pricing.yaml), never hardcoded.

Upstream had one made-up price pair in code, applied to every model. Here each model
has its own price, and the composition root refuses to start when an allowed model
has no price: an unpriced model would cost "zero" and silently bypass the budget.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from rag_observability.core.errors import ConfigurationError


class ModelPrice(BaseModel):
    input_per_million: float = Field(ge=0)
    output_per_million: float = Field(ge=0)


class PriceTable(BaseModel):
    currency: str = "USD"
    models: dict[str, ModelPrice] = Field(default_factory=dict)
    default: ModelPrice | None = None

    def price_for(self, model: str) -> ModelPrice | None:
        if model in self.models:
            return self.models[model]
        # Providers often report a dated snapshot (gpt-4.1-mini-2025-04-14):
        # fall back to the longest configured prefix.
        matches = [name for name in self.models if model.startswith(name)]
        if matches:
            return self.models[max(matches, key=len)]
        return self.default

    def estimate(self, model: str, input_tokens: int, output_tokens: int) -> float:
        price = self.price_for(model)
        if price is None:
            raise ConfigurationError(f"no price configured for model '{model}'")
        cost = (
            input_tokens * price.input_per_million
            + output_tokens * price.output_per_million
        ) / 1_000_000
        return round(cost, 6)

    def ensure_covers(self, models: list[str]) -> None:
        missing = [m for m in models if self.price_for(m) is None]
        if missing:
            raise ConfigurationError(
                "pricing has no entry (and no default) for allowed models: "
                + ", ".join(missing)
            )


def load_price_table(path: Path) -> PriceTable:
    if not Path(path).is_file():
        raise ConfigurationError(f"pricing file not found: {path}")
    try:
        return PriceTable.model_validate(yaml.safe_load(Path(path).read_text("utf-8")) or {})
    except (yaml.YAMLError, ValueError) as exc:
        raise ConfigurationError(f"invalid pricing file {path}: {exc}") from exc
