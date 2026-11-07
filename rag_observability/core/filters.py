"""Filter construction, in the canonical filter DSL (see docs/adr/0006).

The DSL is the Mongo-like dict langchain-postgres understands:
    {"field": "value", "other": {"$in": ["a", "b"]}}
Every VectorIndex adapter must support at least equality and $in.
"""

from typing import Any

from rag_observability.core.errors import ScopeError
from rag_observability.domain.profile import DomainProfile


def resolve_scope(profile: DomainProfile, request_scope: dict[str, Any] | None) -> dict[str, Any]:
    """Enforced filters plus the per-request scope the profile allows.

    A request can add the fields listed in scope.request_fields; it can never
    override an enforced filter nor introduce a field the profile did not declare.
    """
    scope = dict(profile.scope.enforced_filters)
    for field, value in (request_scope or {}).items():
        if field not in profile.scope.request_fields:
            raise ScopeError(f"scope field '{field}' is not allowed by the profile")
        if field in scope:
            raise ScopeError(f"scope field '{field}' is enforced and cannot be overridden")
        if value is not None and value != "":
            scope[field] = value
    missing = [f for f in profile.scope.request_fields if f not in scope]
    if missing:
        # A declared request field that nobody set would silently widen the search.
        raise ScopeError(f"missing request scope: {', '.join(missing)}")
    return scope


def build_filters(
    profile: DomainProfile, scope: dict[str, Any], selections: dict[str, list[str]]
) -> dict[str, Any]:
    filters = dict(scope)
    for facet in profile.facets:
        values = selections.get(facet.name) or []
        if not values:
            # Eliminatory filter: no selection is better than a wrong one.
            continue
        if facet.wildcard:
            # Documents that apply to every value must survive the filter.
            values = [*values, facet.wildcard]
        filters[facet.metadata_field] = {"$in": values}
    return filters


def format_filters(filters: dict) -> str:
    if not filters:
        return "none"
    parts = []
    for key, value in filters.items():
        if isinstance(value, dict) and "$in" in value:
            value = " or ".join(map(str, value["$in"]))
        parts.append(f"{key}={value}")
    return ", ".join(parts)
