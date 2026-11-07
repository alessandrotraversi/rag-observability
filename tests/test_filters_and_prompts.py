import pytest

from rag_observability.core.errors import ScopeError
from rag_observability.core.filters import build_filters, resolve_scope
from rag_observability.core.prompts import PromptSet


def test_filters_keep_scope_and_add_wildcard(fcai_profile):
    scope = resolve_scope(fcai_profile, None)
    filters = build_filters(fcai_profile, scope, {"doc_types": ["sla"], "plan": ["pro"]})
    assert filters == {
        "tenant": "fcai", "product": "fcai-cloud", "status": "published",
        "doc_type": {"$in": ["sla"]}, "plan": {"$in": ["pro", "all"]},
    }
    assert build_filters(fcai_profile, scope, {"doc_types": [], "plan": []}) == scope


def test_request_scope_rules(hr_profile, fcai_profile):
    assert resolve_scope(hr_profile, {"company": "acme-labs"}) == {"status": "approved", "company": "acme-labs"}
    with pytest.raises(ScopeError, match="missing"):
        resolve_scope(hr_profile, None)
    with pytest.raises(ScopeError, match="not allowed"):
        resolve_scope(hr_profile, {"company": "a", "tenant": "b"})
    with pytest.raises(ScopeError):
        resolve_scope(fcai_profile, {"status": "draft"})


def test_prompts_render_domain_without_template_errors(fcai_profile, hr_profile):
    for profile in (fcai_profile, hr_profile):
        prompts = PromptSet(profile)
        text = prompts.planner_prompt("question with {braces}").to_string()
        assert profile.assistant.domain in text
        assert profile.assistant.language in text
        for facet in profile.facets:
            assert facet.name in text
    assert "Não encontrei" in PromptSet(fcai_profile).answer_prompt([], "q").to_string()
