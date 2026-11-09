"""Runtime settings: the *deployment* (providers, endpoints, credentials, policy limits).

What the assistant knows and how it talks lives in the domain profile
(rag_observability/domain/profile.py), not here. Settings answer "where and with what
does it run"; the profile answers "about what".

Nothing here is a module-level singleton: `load_settings()` builds an instance and the
composition root (rag_observability/bootstrap.py) hands it to whoever needs it.
"""

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "staging", "production"]
DEVELOPMENT: Environment = "development"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", populate_by_name=True
    )

    # --- Domain -----------------------------------------------------------------
    profile_path: Path = Field(
        Path("profiles/fcai-saas-support/profile.yaml"), alias="RAG_PROFILE"
    )
    data_dir: Path = Field(Path("data"), alias="RAG_DATA_DIR")
    feature_name: str = Field("rag_chat", alias="RAG_FEATURE")

    # --- Providers ----------------------------------------------------------------
    # Any provider supported by LangChain's init_chat_model / init_embeddings
    # (openai, anthropic, google_genai, bedrock, ollama, azure_openai, ...). The
    # provider package must be installed; credentials may come from the provider's
    # own env vars (OPENAI_API_KEY, ANTHROPIC_API_KEY, ...) or from *_API_KEY below.
    llm_provider: str = Field("openai", alias="LLM_PROVIDER")
    llm_model: str = Field(
        "gpt-4.1-mini", validation_alias=AliasChoices("LLM_MODEL", "OPENAI_CHAT_MODEL")
    )
    llm_api_key: SecretStr | None = Field(None, alias="LLM_API_KEY")
    llm_temperature: float = Field(0.0, alias="LLM_TEMPERATURE")

    embedding_provider: str = Field("openai", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(
        "text-embedding-3-small",
        validation_alias=AliasChoices("EMBEDDING_MODEL", "OPENAI_EMBEDDING_MODEL"),
    )
    embedding_api_key: SecretStr | None = Field(None, alias="EMBEDDING_API_KEY")

    # Built-in name (pgvector | memory) or a dotted path "package.module:Class".
    vector_store: str = Field("pgvector", alias="VECTOR_STORE")
    database_url: str = Field("", alias="DATABASE_URL")

    # --- Observability ------------------------------------------------------------
    app_env: Environment = Field(DEVELOPMENT, alias="APP_ENV")
    observability_enabled: bool = Field(False, alias="OBSERVABILITY_ENABLED")
    observability_sample_rate: float = Field(
        1.0, alias="OBSERVABILITY_SAMPLE_RATE", ge=0.0, le=1.0
    )
    observability_capture_content: bool = Field(
        False, alias="OBSERVABILITY_CAPTURE_CONTENT"
    )
    otel_service_name: str = Field("rag-observability", alias="OTEL_SERVICE_NAME")
    otel_traces_exporter: Literal["console", "otlp"] = Field(
        "console", alias="OTEL_TRACES_EXPORTER"
    )
    otel_exporter_otlp_endpoint: str = Field("", alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    otel_exporter_otlp_headers: str = Field("", alias="OTEL_EXPORTER_OTLP_HEADERS")
    # auto: langfuse when its keys are set, generic OTLP otherwise.
    otel_backend: Literal["auto", "generic", "langfuse"] = Field(
        "auto", alias="OTEL_BACKEND"
    )
    langfuse_public_key: str = Field("", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: SecretStr = Field(SecretStr(""), alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field("http://localhost:3000", alias="LANGFUSE_HOST")

    # --- Governance ---------------------------------------------------------------
    ai_allowed_models: str = Field("gpt-4.1-mini", alias="AI_ALLOWED_MODELS")
    ai_monthly_budget_usd: float = Field(10.0, alias="AI_MONTHLY_BUDGET_USD", ge=0.0)
    ai_max_output_tokens: int = Field(1200, alias="AI_MAX_OUTPUT_TOKENS", gt=0)
    # Built-in name (jsonl | memory | none) or a dotted path "package.module:Class".
    usage_ledger: str = Field("jsonl", alias="AI_USAGE_LEDGER")
    usage_ledger_path: Path = Field(
        Path("data/ai_usage.jsonl"), alias="AI_USAGE_LEDGER_PATH"
    )
    pricing_path: Path = Field(Path("config/pricing.yaml"), alias="AI_PRICING_PATH")

    # --- API ----------------------------------------------------------------------
    # Only enable behind a trusted gateway that sets these headers from the
    # authenticated identity. Never let end users set their own scope.
    api_scope_from_headers: bool = Field(False, alias="API_SCOPE_FROM_HEADERS")

    @property
    def allowed_models(self) -> list[str]:
        # Comma separated, not JSON: AI_ALLOWED_MODELS=gpt-4.1-mini,gpt-4.1
        return [m.strip() for m in self.ai_allowed_models.split(",") if m.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env == DEVELOPMENT

    @property
    def psycopg_dsn(self) -> str:
        return self.database_url.replace("postgresql+psycopg://", "postgresql://")


def load_settings(**overrides) -> Settings:
    """Read the environment (and .env). Keyword overrides use the env var names."""
    return Settings(**overrides)
