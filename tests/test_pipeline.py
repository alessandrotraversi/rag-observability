import json

from conftest import FAKE_MODEL, FakeStep, build_pipeline, make_settings

from rag_observability.core.results import RagAnswer, RerankResult
from rag_observability.domain.query_plan import build_query_plan_model
from rag_observability.governance.ledgers import InMemoryUsageLedger


def _planner(profile, **fields):
    Plan = build_query_plan_model(profile)
    defaults = {"normalized_question": "", "needs_clarification": False}
    return FakeStep(lambda prompt: Plan(**{**defaults, **fields}))


def _rerank_all():
    def respond(prompt):
        text = prompt.to_string()
        ids = [line.split("Chunk ID: ")[1].rstrip("]") for line in text.splitlines() if "Chunk ID: " in line]
        return RerankResult(selected_chunk_ids=ids)
    return FakeStep(respond)


def _answer_citing(extra_ids=()):
    def respond(prompt):
        text = prompt.to_string()
        ids = [line.split("Chunk ID: ")[1].rstrip("]") for line in text.splitlines() if "Chunk ID: " in line]
        return RagAnswer(answer="resposta", has_answer=True, used_chunk_ids=ids[:1] + list(extra_ids))
    return FakeStep(respond)


def test_happy_path_fcai(tmp_path, fcai_profile):
    ledger = InMemoryUsageLedger()
    pipeline = build_pipeline(
        fcai_profile, make_settings(tmp_path),
        _planner(fcai_profile, normalized_question="SLA incidentes P1 plano Enterprise",
                 doc_types=["sla", "plan"], plan="enterprise", exact_terms=["P1"]),
        _rerank_all(), _answer_citing(extra_ids=["invented-id"]), ledger=ledger,
    )
    result = pipeline.run("Qual é o SLA para P1 no Enterprise?", include_debug=True)

    assert result.has_answer and len(result.sources) == 1  # invented id dropped
    debug = result.debug
    assert debug.query_plan.filters["plan"] == {"$in": ["enterprise", "all"]}
    assert {c.source_file for c in debug.retrieved_chunks} <= {
        "product-support-sla.md", "enterprise-plan.md", "pro-plan.md", "starter-plan.md"}
    assert all(c.attributes.get("version") for c in debug.retrieved_chunks)
    assert debug.model_usage[0].model == FAKE_MODEL
    assert debug.model_usage[0].input_tokens == 300  # planner + reranker + answer
    assert len(ledger.records) == 1 and ledger.records[0].scope == {"tenant": "fcai", "product": "fcai-cloud"}
    assert debug.estimated_cost_usd == ledger.records[0].estimated_cost_usd > 0


def test_retrieval_respects_facet_filter(tmp_path, fcai_profile):
    pipeline = build_pipeline(
        fcai_profile, make_settings(tmp_path),
        _planner(fcai_profile, normalized_question="preço", doc_types=["plan"], plan="pro"),
        _rerank_all(), _answer_citing(),
    )
    debug = pipeline.run("preço do pro", include_debug=True).debug
    files = {c.source_file for c in debug.retrieved_chunks}
    assert files == {"pro-plan.md"}


def test_clarification_stops_before_retrieval(tmp_path, fcai_profile):
    answerer = _answer_citing()
    pipeline = build_pipeline(
        fcai_profile, make_settings(tmp_path),
        _planner(fcai_profile, normalized_question="x", needs_clarification=True,
                 clarification_question="Qual plano?"),
        _rerank_all(), answerer,
    )
    result = pipeline.run("plano da empresa?", include_debug=True)
    assert result.needs_clarification and result.answer == "Qual plano?"
    assert result.debug.retrieved_chunks == [] and answerer.calls == []


def test_empty_rerank_skips_answer_model(tmp_path, fcai_profile):
    answerer = _answer_citing()
    pipeline = build_pipeline(
        fcai_profile, make_settings(tmp_path),
        _planner(fcai_profile, normalized_question="capital da França"),
        FakeStep(lambda p: RerankResult(selected_chunk_ids=[])), answerer,
    )
    result = pipeline.run("Qual é a capital da França?")
    assert not result.has_answer and result.answer == fcai_profile.messages.no_answer
    assert answerer.calls == [] and result.debug is None


def test_policy_blocks_before_any_model_call(tmp_path, fcai_profile):
    planner = _planner(fcai_profile, normalized_question="x")
    ledger = InMemoryUsageLedger()
    pipeline = build_pipeline(fcai_profile, make_settings(tmp_path), planner,
                              _rerank_all(), _answer_citing(), budget=0.0, ledger=ledger)
    result = pipeline.run("qualquer coisa", include_debug=True)
    assert result.policy_blocked and result.answer == fcai_profile.messages.policy_blocked
    assert result.debug.policy.reason == "monthly budget reached"
    assert planner.calls == [] and ledger.records == []


def test_budget_closes_the_loop(tmp_path, fcai_profile):
    ledger = InMemoryUsageLedger()
    pipeline = build_pipeline(
        fcai_profile, make_settings(tmp_path),
        _planner(fcai_profile, normalized_question="SLA"), _rerank_all(), _answer_citing(),
        budget=0.0004, ledger=ledger,
    )
    assert not pipeline.run("SLA?").policy_blocked  # spends 0.00042
    assert pipeline.run("SLA?").policy_blocked


def test_second_domain_with_request_scope(tmp_path, hr_profile):
    pipeline = build_pipeline(
        hr_profile, make_settings(tmp_path),
        _planner(hr_profile, normalized_question="vacation days Portugal", topics=["leave"], country="pt"),
        _rerank_all(), _answer_citing(),
    )
    result = pipeline.run("How many vacation days in Portugal?",
                          scope={"company": "acme-labs"}, include_debug=True)
    files = {c.source_file for c in result.debug.retrieved_chunks}
    assert "leave-portugal.md" in files
    assert "leave-brazil.md" not in files
    assert "draft-sabbatical.md" not in files  # enforced status=approved
    assert result.sources[0].attributes.get("updated")


def test_run_log_has_no_content(tmp_path, fcai_profile, caplog):
    pipeline = build_pipeline(
        fcai_profile, make_settings(tmp_path),
        _planner(fcai_profile, normalized_question="SLA P1"), _rerank_all(), _answer_citing(),
    )
    with caplog.at_level("INFO", logger="rag_observability.pipeline"):
        pipeline.run("pergunta secreta do usuário")
    record = json.loads(caplog.records[-1].getMessage())
    assert "pergunta secreta" not in caplog.text and "resposta" not in caplog.text
    assert record["policy_allowed"] is True and record["profile"] == "fcai-saas-support"
