"""Chat and embedding models, for any provider LangChain supports.

Upstream pinned `model_provider="openai"` and OPENAI_API_KEY. Here provider and model
are settings; init_chat_model / init_embeddings pick the integration package
(langchain-openai, langchain-anthropic, langchain-google-genai, langchain-ollama, ...),
which must be installed (docs/adr/0005).
"""

from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from rag_observability.core.errors import ConfigurationError
from rag_observability.settings import Settings


def build_chat_model(settings: Settings, max_tokens: int) -> BaseChatModel:
    kwargs = {"temperature": settings.llm_temperature, "max_tokens": max_tokens}
    if settings.llm_api_key:
        kwargs["api_key"] = settings.llm_api_key.get_secret_value()
    try:
        return init_chat_model(
            settings.llm_model, model_provider=settings.llm_provider, **kwargs
        )
    except ImportError as exc:
        raise ConfigurationError(
            f"chat provider '{settings.llm_provider}' needs its integration package: {exc}"
        ) from exc


def build_embeddings(settings: Settings) -> Embeddings:
    kwargs = {}
    if settings.embedding_api_key:
        kwargs["api_key"] = settings.embedding_api_key.get_secret_value()
    try:
        return init_embeddings(
            settings.embedding_model, provider=settings.embedding_provider, **kwargs
        )
    except ImportError as exc:
        raise ConfigurationError(
            f"embedding provider '{settings.embedding_provider}' needs its "
            f"integration package: {exc}"
        ) from exc
