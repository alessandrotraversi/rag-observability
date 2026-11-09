"""OpenTelemetry instrumentation, isolated in this module.

Same contract as upstream:
- the application depends on OpenTelemetry only, never on a backend SDK;
- with OBSERVABILITY_ENABLED=false no provider is configured and every span is a no-op;
- only safe attributes are recorded (ids, counts, flags, filters, timings, tokens);
  the question and the final answer travel as debug *events*, in development only;
- prompts, context, chunk contents, documents and credentials never leave.

What changed: state lives in a `Telemetry` object built from Settings (no global
settings import), the environment policy raises a typed error instead of exiting,
and the provider is flushed at exit so short-lived CLIs do not lose batched spans.
"""

import atexit
import json
import logging
from contextlib import contextmanager
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanProcessor,
)
from opentelemetry.sdk.trace.sampling import ParentBased, Sampler, TraceIdRatioBased
from opentelemetry.trace import Span, Status, StatusCode

from rag_observability import __version__
from rag_observability.core.errors import ConfigurationError
from rag_observability.observability import conventions as conv
from rag_observability.observability.backends import otlp_endpoint
from rag_observability.settings import Settings

TRACER_NAME = "rag_observability"
TRACES_PATH = "/v1/traces"

log = logging.getLogger("rag_observability.telemetry")

_provider_configured = False


def validate_observability_policy(settings: Settings) -> None:
    """Refuse a policy that does not hold for the environment, even with tracing off."""
    if settings.observability_capture_content and not settings.is_development:
        raise ConfigurationError(
            "Invalid observability policy: OBSERVABILITY_CAPTURE_CONTENT "
            "can only be true in development."
        )


class Telemetry:
    def __init__(self, settings: Settings) -> None:
        validate_observability_policy(settings)
        self.settings = settings

    # --- policy ---------------------------------------------------------------
    @property
    def sample_rate(self) -> float:
        # Development always traces everything; the other environments decide.
        return 1.0 if self.settings.is_development else self.settings.observability_sample_rate

    @property
    def capture_content(self) -> bool:
        return self.settings.is_development and self.settings.observability_capture_content

    # --- setup ----------------------------------------------------------------
    def setup(self) -> None:
        """Configure the global tracer provider once. Without it spans are no-ops."""
        global _provider_configured
        if _provider_configured or not self.settings.observability_enabled:
            return
        _provider_configured = True

        provider = TracerProvider(
            resource=Resource.create(
                {
                    SERVICE_NAME: self.settings.otel_service_name,
                    SERVICE_VERSION: __version__,
                    "deployment.environment.name": self.settings.app_env,
                }
            ),
            # ParentBased: steps follow the pipeline's decision; never half a trace.
            sampler=self._sampler(),
        )
        provider.add_span_processor(self._processor())
        trace.set_tracer_provider(provider)
        # Batched spans of a CLI that exits right away would otherwise be lost.
        atexit.register(provider.shutdown)
        self._announce()

    def _sampler(self) -> Sampler:
        return ParentBased(TraceIdRatioBased(self.sample_rate))

    def _processor(self) -> SpanProcessor:
        if self.settings.otel_traces_exporter == "otlp":
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            backend, (endpoint, headers) = otlp_endpoint(self.settings)
            names = ", ".join(sorted(headers)) or "none"  # names only: values are secrets
            log.warning(
                "Traces to %s via %s preset (headers: %s).",
                endpoint or "the OTLP default endpoint", backend, names,
            )
            return BatchSpanProcessor(
                OTLPSpanExporter(endpoint=_traces_url(endpoint), headers=headers or None)
            )
        return SimpleSpanProcessor(ConsoleSpanExporter())

    def _announce(self) -> None:
        s = self.settings
        log.warning(
            "Observability enabled. environment=%s exporter=%s sample_rate=%s capture_content=%s",
            s.app_env, s.otel_traces_exporter, self.sample_rate,
            str(self.capture_content).lower(),
        )

    # --- spans ----------------------------------------------------------------
    @contextmanager
    def span(self, name: str) -> Iterator[Span]:
        """Open a span; spans opened inside it become its children."""
        tracer = trace.get_tracer(TRACER_NAME, __version__)
        with tracer.start_as_current_span(
            name, record_exception=False, set_status_on_exception=False
        ) as current:
            try:
                yield current
            except Exception as exc:
                # Error type and message only: no stack trace, no payload.
                current.set_status(Status(StatusCode.ERROR, f"{type(exc).__name__}: {exc}"))
                current.set_attribute("error.type", type(exc).__name__)
                raise

    @staticmethod
    def set_attributes(span: Span, attributes: dict[str, Any]) -> None:
        """Record safe attributes. None values are left out."""
        if not span.is_recording():
            return
        span.set_attributes(
            {name: _attribute_value(v) for name, v in attributes.items() if v is not None}
        )

    def record_debug_content(
        self, span: Span, question: str | None = None, answer: str | None = None
    ) -> None:
        """Question and answer as events, only when development asks for them."""
        if not self.capture_content or not span.is_recording():
            return
        if question:
            span.add_event(conv.DEBUG_QUESTION_EVENT, {conv.DEBUG_QUESTION_EVENT: question})
        if answer:
            span.add_event(conv.DEBUG_ANSWER_EVENT, {conv.DEBUG_ANSWER_EVENT: answer})


def _attribute_value(value: Any) -> Any:
    # Attributes are primitives or homogeneous sequences; dicts go in as JSON.
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


def _traces_url(endpoint: str) -> str | None:
    if not endpoint:
        return None  # the exporter falls back to its own OTEL_* defaults
    endpoint = endpoint.rstrip("/")
    return endpoint if endpoint.endswith(TRACES_PATH) else endpoint + TRACES_PATH
