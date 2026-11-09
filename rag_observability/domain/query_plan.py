"""The QueryPlan model, generated from the profile's facets.

Upstream declared `DocType = Literal[...]` and `Plan = Literal[...]` by hand. Here the
structured-output schema is built at startup from the facets, so the model can only
return values the profile (and therefore the index) knows. A new domain is a new YAML,
not a new class.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, create_model

from rag_observability.domain.profile import DomainProfile, Facet


class BaseQueryPlan(BaseModel):
    """Fields every plan has, whatever the domain."""

    normalized_question: str = Field(
        description="The question rewritten to retrieve better, self-contained."
    )
    exact_terms: list[str] = Field(
        default_factory=list, description="Literal terms that matter for retrieval."
    )
    needs_clarification: bool = Field(
        description="True only if the question has more than one reasonable reading."
    )
    clarification_question: str | None = Field(
        default=None, description="Clarification question, when needed."
    )


def _facet_field(facet: Facet) -> tuple[Any, Any]:
    allowed = Literal[tuple(facet.values)]  # type: ignore[valid-type]
    description = facet.description or f"Filter on '{facet.metadata_field}'."
    if facet.multiple:
        return list[allowed], Field(default_factory=list, description=description)
    return Optional[allowed], Field(default=None, description=description)


def build_query_plan_model(profile: DomainProfile) -> type[BaseQueryPlan]:
    fields = {facet.name: _facet_field(facet) for facet in profile.facets}
    return create_model("QueryPlan", __base__=BaseQueryPlan, **fields)


def facet_selections(plan: BaseQueryPlan, profile: DomainProfile) -> dict[str, list[str]]:
    """What the plan chose on each facet, normalized to lists (empty = no filter)."""
    selections: dict[str, list[str]] = {}
    for facet in profile.facets:
        value = getattr(plan, facet.name, None)
        if value is None:
            selections[facet.name] = []
        elif isinstance(value, list):
            selections[facet.name] = list(dict.fromkeys(value))
        else:
            selections[facet.name] = [value]
    return selections


def build_search_query(plan: BaseQueryPlan) -> str:
    # The exact terms ride along in the embedded text, so literals the rewrite may
    # have dropped (P1, SCIM, 99.9%) still reach the search.
    return " ".join([plan.normalized_question, *plan.exact_terms])
