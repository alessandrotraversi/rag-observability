"""The domain profile: everything that makes the assistant about *something*.

The upstream project hardcoded its domain (a fictional SaaS called FCAI) in Python:
the tenant/product filters, the DocType/Plan literals, the planner catalog, the
required front matter, the table name and the Portuguese messages. Here all of that is
declared in one YAML file, validated at startup, and the code stays domain-free.

A profile describes:
- assistant: who answers, for which domain, in which language;
- scope: authorization filters the application enforces (never the model);
- facets: metadata dimensions the planner may filter by, with their allowed values;
- planner: extra guidance and few-shot examples for this domain;
- ingestion / retrieval / sources: how documents are chunked, fetched and cited;
- messages: the fixed answers (no answer, clarification fallback, policy blocked).
"""

import keyword
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from rag_observability.core.errors import ConfigurationError

# Field names the generated QueryPlan already uses; a facet cannot take them.
RESERVED_PLAN_FIELDS = {
    "normalized_question",
    "exact_terms",
    "needs_clarification",
    "clarification_question",
}


class Assistant(BaseModel):
    domain: str = Field(description="Short name of the domain, used in the prompts.")
    persona: str = Field("an assistant", description="Who answers, e.g. 'a support assistant'.")
    language: str = Field("English", description="Language of answers and rewrites.")


class Facet(BaseModel):
    """One metadata dimension the planner may filter by (a closed vocabulary)."""

    name: str
    field: str | None = Field(None, description="Metadata field; defaults to name.")
    description: str = ""
    multiple: bool = Field(
        False, description="True: the planner lists every value that could apply."
    )
    values: dict[str, str] = Field(description="Allowed value -> what it covers.")
    # Documents tagged with this value match any selection on the facet
    # (e.g. plan=all applies to every plan). The planner never chooses it.
    wildcard: str | None = None

    @property
    def metadata_field(self) -> str:
        return self.field or self.name

    @field_validator("name")
    @classmethod
    def _identifier(cls, value: str) -> str:
        if not value.isidentifier() or keyword.iskeyword(value):
            raise ValueError(f"facet name '{value}' must be a valid identifier")
        if value in RESERVED_PLAN_FIELDS:
            raise ValueError(f"facet name '{value}' is reserved")
        return value

    @field_validator("field")
    @classmethod
    def _field_identifier(cls, value: str | None) -> str | None:
        # Metadata fields end up in filter expressions (e.g. JSON paths in SQL).
        if value is not None and not value.isidentifier():
            raise ValueError(f"facet field '{value}' must be a valid identifier")
        return value

    @field_validator("values")
    @classmethod
    def _non_empty(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("a facet needs at least one value")
        return value


class Scope(BaseModel):
    # Always applied, for every request. Authorization, not search.
    enforced_filters: dict[str, Any] = Field(default_factory=dict)
    # Fields a trusted caller may set per request (e.g. tenant from the auth token).
    request_fields: list[str] = Field(default_factory=list)
    # Which scope fields become span attributes and ledger keys.
    observed_fields: list[str] | None = None


class Planner(BaseModel):
    guidance: list[str] = Field(default_factory=list)
    clarification_guidance: str = ""
    examples: list[str] = Field(default_factory=list)


class ContextHeaderField(BaseModel):
    label: str
    field: str


class Ingestion(BaseModel):
    loader: str = "markdown"
    source_dir: Path = Path("knowledge_base")
    glob: str = "*.md"
    required_metadata: list[str] = Field(default_factory=lambda: ["title"])
    context_header: list[ContextHeaderField] = Field(
        default_factory=lambda: [
            ContextHeaderField(label="Document title", field="title"),
            ContextHeaderField(label="Section", field="section"),
        ]
    )
    split_headers: list[str] = Field(default_factory=lambda: ["#", "##", "###"])
    chunk_size: int = Field(900, gt=0)
    chunk_overlap: int = Field(150, ge=0)


class Retrieval(BaseModel):
    top_k: int = Field(8, gt=0)
    rerank_top_n: int = Field(4, gt=0)
    preview_chars: int = Field(300, gt=0)


class Sources(BaseModel):
    # Extra metadata fields exposed on each cited source, besides file/title/section.
    extra_fields: list[str] = Field(default_factory=list)


class Messages(BaseModel):
    no_answer: str = (
        "I could not find enough information in the knowledge base to answer safely."
    )
    clarification_fallback: str = "Could you give more details about your question?"
    policy_blocked: str = (
        "This request cannot be processed because it exceeds an operational policy."
    )


class DomainProfile(BaseModel):
    name: str
    description: str = ""
    collection: str = Field(description="Vector store collection / table name.")
    assistant: Assistant
    scope: Scope = Field(default_factory=Scope)
    facets: list[Facet] = Field(default_factory=list)
    planner: Planner = Field(default_factory=Planner)
    ingestion: Ingestion = Field(default_factory=Ingestion)
    retrieval: Retrieval = Field(default_factory=Retrieval)
    sources: Sources = Field(default_factory=Sources)
    messages: Messages = Field(default_factory=Messages)

    # Set by load_profile: relative paths in the profile resolve against it.
    base_dir: Path = Field(default_factory=Path.cwd, exclude=True)

    @field_validator("collection")
    @classmethod
    def _safe_collection(cls, value: str) -> str:
        # It ends up as an SQL identifier in some adapters.
        if not value.replace("_", "").isalnum() or not value[0].isalpha():
            raise ValueError("collection must be alphanumeric/underscore, starting with a letter")
        return value

    @model_validator(mode="after")
    def _consistency(self) -> "DomainProfile":
        names = [facet.name for facet in self.facets]
        if len(names) != len(set(names)):
            raise ValueError("facet names must be unique")
        clash = set(self.scope.enforced_filters) & {f.metadata_field for f in self.facets}
        if clash:
            # The model must never be able to widen or narrow an authorization filter.
            raise ValueError(f"facets cannot filter on enforced scope fields: {sorted(clash)}")
        if self.retrieval.rerank_top_n > self.retrieval.top_k:
            raise ValueError("retrieval.rerank_top_n cannot exceed retrieval.top_k")
        return self

    @property
    def source_dir(self) -> Path:
        path = self.ingestion.source_dir
        return path if path.is_absolute() else self.base_dir / path

    @property
    def observed_scope_fields(self) -> list[str]:
        if self.scope.observed_fields is not None:
            return self.scope.observed_fields
        return [*self.scope.enforced_filters, *self.scope.request_fields]

    def facet(self, name: str) -> Facet:
        for facet in self.facets:
            if facet.name == name:
                return facet
        raise KeyError(name)


def load_profile(path: Path) -> DomainProfile:
    path = Path(path)
    if not path.is_file():
        raise ConfigurationError(f"domain profile not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return DomainProfile.model_validate({**raw, "base_dir": path.resolve().parent})
    except (yaml.YAMLError, ValueError) as exc:
        raise ConfigurationError(f"invalid domain profile {path}: {exc}") from exc
