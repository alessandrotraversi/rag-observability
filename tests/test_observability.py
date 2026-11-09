import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from conftest import build_pipeline, make_settings
from test_pipeline import _answer_citing, _planner, _rerank_all

from rag_observability.core.errors import ConfigurationError
from rag_observability.observability import conventions as conv
from rag_observability.observability import tracing
from rag_observability.observability.backends import otlp_endpoint
from rag_observability.observability.tracing import Telemetry


@pytest.fixture
def spans(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tracing.trace, "get_tracer",
                        lambda name, version=None: provider.get_tracer(name, version))
    return exporter


def test_capture_content_refused_outside_development(tmp_path):
    with pytest.raises(ConfigurationError):
        Telemetry(make_settings(tmp_path, APP_ENV="production", OBSERVABILITY_CAPTURE_CONTENT="true"))


def test_sample_rate_policy(tmp_path):
    assert Telemetry(make_settings(tmp_path, OBSERVABILITY_SAMPLE_RATE="0.1")).sample_rate == 1.0
    assert Telemetry(make_settings(tmp_path, APP_ENV="staging", OBSERVABILITY_SAMPLE_RATE="0.1")).sample_rate == 0.1


def test_spans_and_genai_attributes(tmp_path, fcai_profile, spans):
    pipeline = build_pipeline(
        fcai_profile, make_settings(tmp_path),
        _planner(fcai_profile, normalized_question="SLA P1", doc_types=["sla"]),
        _rerank_all(), _answer_citing(),
    )
    pipeline.run("pergunta")
    by_name = {s.name: s for s in spans.get_finished_spans()}
    assert set(by_name) == {conv.PIPELINE_SPAN, conv.QUERY_PLANNING_SPAN, conv.RETRIEVAL_SPAN,
                            conv.RERANKING_SPAN, conv.ANSWER_GENERATION_SPAN}
    for name in (conv.QUERY_PLANNING_SPAN, conv.RERANKING_SPAN, conv.ANSWER_GENERATION_SPAN):
        attrs = by_name[name].attributes
        assert attrs[conv.OPERATION_NAME] == "chat" and attrs[conv.INPUT_TOKENS] == 100
    root = by_name[conv.PIPELINE_SPAN].attributes
    assert root[conv.scope_attribute("tenant")] == "fcai"
    assert by_name[conv.QUERY_PLANNING_SPAN].attributes[conv.facet_attribute("doc_types")] == ("sla",)
    flat = str([dict(s.attributes) for s in spans.get_finished_spans()])
    assert "pergunta" not in flat  # content is never an attribute
    assert not by_name[conv.PIPELINE_SPAN].events  # capture_content off


def test_debug_events_only_when_enabled(tmp_path, fcai_profile, spans):
    pipeline = build_pipeline(
        fcai_profile, make_settings(tmp_path, OBSERVABILITY_CAPTURE_CONTENT="true"),
        _planner(fcai_profile, normalized_question="SLA"), _rerank_all(), _answer_citing(),
    )
    pipeline.run("pergunta")
    root = next(s for s in spans.get_finished_spans() if s.name == conv.PIPELINE_SPAN)
    assert [e.name for e in root.events] == [conv.DEBUG_QUESTION_EVENT, conv.DEBUG_ANSWER_EVENT]


def test_backend_presets(tmp_path):
    name, (endpoint, headers) = otlp_endpoint(make_settings(
        tmp_path, OTEL_EXPORTER_OTLP_ENDPOINT="http://collector:4318",
        OTEL_EXPORTER_OTLP_HEADERS="x-api-key=abc"))
    assert name == "generic" and endpoint == "http://collector:4318" and headers == {"x-api-key": "abc"}

    name, (endpoint, headers) = otlp_endpoint(make_settings(
        tmp_path, LANGFUSE_PUBLIC_KEY="pk", LANGFUSE_SECRET_KEY="sk", LANGFUSE_HOST="http://lf:3000/"))
    assert name == "langfuse" and endpoint == "http://lf:3000/api/public/otel"
    assert headers["authorization"].startswith("Basic ") and headers["x-langfuse-ingestion-version"] == "4"
