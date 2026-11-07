"""OTLP backend presets: how an endpoint + headers are derived per backend.

The core speaks only OpenTelemetry. A preset is a small pure function that turns
settings into (endpoint, headers) — upstream had Langfuse as a special case inside
the exporter; here it is one preset among others, and adding Phoenix, Honeycomb, a
Collector, ... is adding a function to PRESETS (docs/adr/0009).
"""

from base64 import b64encode
from typing import Callable

from opentelemetry.util.re import parse_env_headers

from rag_observability.settings import Settings

Endpoint = tuple[str, dict[str, str]]

LANGFUSE_OTEL_PATH = "/api/public/otel"
LANGFUSE_INGESTION_HEADER = "x-langfuse-ingestion-version"
LANGFUSE_INGESTION_VERSION = "4"


def configured_headers(settings: Settings) -> dict[str, str]:
    if not settings.otel_exporter_otlp_headers:
        return {}
    # liberal: a hand-pasted "Authorization=Basic abc" has a space.
    return dict(parse_env_headers(settings.otel_exporter_otlp_headers, liberal=True))


def generic(settings: Settings) -> Endpoint:
    return settings.otel_exporter_otlp_endpoint, configured_headers(settings)


def langfuse(settings: Settings) -> Endpoint:
    headers = configured_headers(settings)
    keys = f"{settings.langfuse_public_key}:{settings.langfuse_secret_key.get_secret_value()}"
    # A header set by hand is never overwritten.
    headers.setdefault("authorization", f"Basic {b64encode(keys.encode()).decode()}")
    headers.setdefault(LANGFUSE_INGESTION_HEADER, LANGFUSE_INGESTION_VERSION)
    return settings.langfuse_host.rstrip("/") + LANGFUSE_OTEL_PATH, headers


PRESETS: dict[str, Callable[[Settings], Endpoint]] = {
    "generic": generic,
    "langfuse": langfuse,
}


def resolve_backend(settings: Settings) -> str:
    if settings.otel_backend != "auto":
        return settings.otel_backend
    has_langfuse = settings.langfuse_public_key and settings.langfuse_secret_key.get_secret_value()
    return "langfuse" if has_langfuse else "generic"


def otlp_endpoint(settings: Settings) -> tuple[str, Endpoint]:
    name = resolve_backend(settings)
    return name, PRESETS[name](settings)
