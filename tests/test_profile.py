import pytest

from rag_observability.core.errors import ConfigurationError
from rag_observability.domain.profile import DomainProfile, load_profile
from rag_observability.domain.query_plan import build_query_plan_model, facet_selections


def test_both_example_profiles_load(fcai_profile, hr_profile):
    assert fcai_profile.facet("plan").wildcard == "all"
    assert hr_profile.scope.request_fields == ["company"]


def test_query_plan_schema_comes_from_facets(fcai_profile):
    Plan = build_query_plan_model(fcai_profile)
    plan = Plan(normalized_question="q", doc_types=["sla", "plan", "sla"], plan="pro",
                needs_clarification=False)
    assert facet_selections(plan, fcai_profile) == {"doc_types": ["sla", "plan"], "plan": ["pro"]}
    with pytest.raises(ValueError):
        Plan(normalized_question="q", doc_types=["invented"], needs_clarification=False)
    with pytest.raises(ValueError):
        Plan(normalized_question="q", plan="all", needs_clarification=False)  # wildcard is not choosable


def _minimal(**overrides):
    data = {"name": "x", "collection": "x", "assistant": {"domain": "X"}}
    data.update(overrides)
    return data


def test_facet_cannot_touch_enforced_scope():
    with pytest.raises(ValueError, match="enforced scope"):
        DomainProfile.model_validate(_minimal(
            scope={"enforced_filters": {"tenant": "a"}},
            facets=[{"name": "tenant", "values": {"a": "", "b": ""}}],
        ))


def test_reserved_and_invalid_names():
    with pytest.raises(ValueError):
        DomainProfile.model_validate(_minimal(facets=[{"name": "exact_terms", "values": {"a": ""}}]))
    with pytest.raises(ValueError):
        DomainProfile.model_validate(_minimal(collection="drop table;"))


def test_missing_profile_is_a_configuration_error(tmp_path):
    with pytest.raises(ConfigurationError):
        load_profile(tmp_path / "nope.yaml")
