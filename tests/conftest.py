"""Fakes that let the whole pipeline run offline: no API key, no database."""

import hashlib
import math
import re
from pathlib import Path

import pytest
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from rag_observability.core.pipeline import ModelSteps, RagPipeline
from rag_observability.domain.profile import load_profile
from rag_observability.governance.ledgers import InMemoryUsageLedger
from rag_observability.governance.policy import PolicyEngine
from rag_observability.governance.pricing import ModelPrice, PriceTable
from rag_observability.ingestion.chunking import chunk_document, validate_metadata
from rag_observability.ingestion.loaders import load_markdown_documents
from rag_observability.observability.tracing import Telemetry
from rag_observability.settings import Settings
from rag_observability.vectorstores.memory import InMemoryIndex

ROOT = Path(__file__).resolve().parent.parent
FAKE_MODEL = "fake-model"


class HashEmbeddings(Embeddings):
    """Bag-of-words hashed into 256 dims: deterministic, lexical, good enough for tests."""

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * 256
        for token in re.findall(r"\w+", text.lower()):
            vector[int(hashlib.md5(token.encode()).hexdigest(), 16) % 256] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts):
        return [self._embed(t) for t in texts]

    def embed_query(self, text):
        return self._embed(text)


class FakeStep:
    """Stands in for model.with_structured_output(...): returns scripted outputs
    and reports token usage through the callbacks, like a real chat model."""

    def __init__(self, responder, input_tokens=100, output_tokens=20):
        self.responder = responder
        self.calls = []
        self.input_tokens, self.output_tokens = input_tokens, output_tokens

    def invoke(self, prompt, config=None):
        self.calls.append(prompt)
        message = AIMessage(
            content="",
            usage_metadata={
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.input_tokens + self.output_tokens,
            },
            response_metadata={"model_name": FAKE_MODEL},
        )
        for handler in (config or {}).get("callbacks", []):
            if isinstance(handler, UsageMetadataCallbackHandler):
                handler.on_llm_end(LLMResult(generations=[[ChatGeneration(message=message)]]))
        return self.responder(prompt)


def make_settings(tmp_path, **env) -> Settings:
    base = {
        "RAG_DATA_DIR": str(tmp_path),
        "LLM_MODEL": FAKE_MODEL,
        "AI_ALLOWED_MODELS": FAKE_MODEL,
        "VECTOR_STORE": "memory",
        "AI_USAGE_LEDGER": "memory",
    }
    base.update(env)
    return Settings(_env_file=None, **base)


def indexed_memory(profile, path=None) -> InMemoryIndex:
    index = InMemoryIndex(None, profile, HashEmbeddings(), path=path)
    index.reset()
    chunks = []
    for document in load_markdown_documents(profile):
        validate_metadata(document, profile)
        chunks.extend(chunk_document(document, profile))
    from langchain_core.documents import Document

    docs = [Document(page_content=c["content"], metadata=c["metadata"]) for c in chunks]
    index.upsert(docs, [d.metadata["chunk_id"] for d in docs])
    return index


@pytest.fixture
def fcai_profile():
    return load_profile(ROOT / "profiles/fcai-saas-support/profile.yaml")


@pytest.fixture
def hr_profile():
    return load_profile(ROOT / "profiles/hr-handbook/profile.yaml")


def build_pipeline(profile, settings, planner, reranker, answerer, budget=10.0, ledger=None):
    ledger = ledger if ledger is not None else InMemoryUsageLedger()
    prices = PriceTable(models={FAKE_MODEL: ModelPrice(input_per_million=1.0, output_per_million=2.0)})
    policy = PolicyEngine([FAKE_MODEL], budget, 500, ledger, prices)
    steps = ModelSteps(planner=planner, reranker=reranker, answerer=answerer,
                       provider="fake", model=FAKE_MODEL, temperature=0, max_tokens=500)
    return RagPipeline(profile=profile, index=indexed_memory(profile), steps=steps,
                       policy=policy, telemetry=Telemetry(settings))
