from fastapi.testclient import TestClient

from conftest import build_pipeline, make_settings
from test_pipeline import _answer_citing, _planner, _rerank_all

from rag_observability.api import create_app, header_scope
from rag_observability.bootstrap import Container


def _client(tmp_path, profile, **planner_fields):
    settings = make_settings(tmp_path)
    pipeline = build_pipeline(profile, settings,
                              _planner(profile, normalized_question="q", **planner_fields),
                              _rerank_all(), _answer_citing())
    container = Container(settings, profile, pipeline.telemetry, pipeline)
    return TestClient(create_app(container, scope_resolver=header_scope))


def test_chat_and_validation(tmp_path, fcai_profile):
    client = _client(tmp_path, fcai_profile)
    assert client.get("/health").json()["profile"] == "fcai-saas-support"
    assert client.post("/chat", json={"question": "  "}).status_code == 400
    body = client.post("/chat", json={"question": "SLA P1?"}).json()
    assert body["has_answer"] and "debug" not in body and body["request_id"]


def test_scope_from_trusted_headers(tmp_path, hr_profile):
    client = _client(tmp_path, hr_profile, topics=["leave"])
    assert client.post("/chat", json={"question": "vacation?"}).status_code == 403
    ok = client.post("/chat", json={"question": "vacation?", "debug": True},
                     headers={"X-RAG-Scope-Company": "acme-labs"})
    assert ok.status_code == 200
    assert ok.json()["debug"]["policy"]["scope"] == {"company": "acme-labs"}
