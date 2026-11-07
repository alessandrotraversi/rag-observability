from datetime import datetime, timezone

import pytest

from conftest import ROOT, HashEmbeddings, make_settings

from rag_observability.core.errors import ConfigurationError, IndexContractError, IngestionError
from rag_observability.governance.ledgers import JsonlUsageLedger
from rag_observability.governance.models import UsageRecord
from rag_observability.governance.pricing import load_price_table
from rag_observability.ingestion.chunking import validate_metadata
from rag_observability.ingestion.index import index_chunks
from rag_observability.ingestion.ingest import ingest
from rag_observability.ingestion.loaders import SourceDocument
from rag_observability.vectorstores.memory import InMemoryIndex, matches


def test_pricing_file_and_coverage():
    prices = load_price_table(ROOT / "config/pricing.yaml")
    assert prices.price_for("gpt-4.1-mini-2025-04-14") == prices.models["gpt-4.1-mini"]  # prefix
    with pytest.raises(ConfigurationError):
        prices.ensure_covers(["unknown-model"])
    assert prices.estimate("gpt-4.1-mini", 1_000_000, 0) == prices.models["gpt-4.1-mini"].input_per_million


def test_jsonl_ledger_month_and_scope(tmp_path):
    ledger = JsonlUsageLedger(tmp_path / "u.jsonl")
    def rec(ts, scope, cost):
        return UsageRecord(request_id="r", timestamp=ts, feature="f", scope=scope, provider="p",
                           model="m", input_tokens=1, output_tokens=1, total_tokens=2,
                           estimated_cost_usd=cost)
    ledger.record(rec("2026-10-31T23:00:00+00:00", {"tenant": "a"}, 5.0))
    ledger.record(rec("2026-11-02T10:00:00+00:00", {"tenant": "a"}, 1.0))
    ledger.record(rec("2026-11-03T10:00:00+00:00", {"tenant": "b"}, 2.0))
    since = datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert ledger.spend_since(since, "f", {"tenant": "a"}) == 1.0
    assert ledger.spend_since(since, "f", {}) == 3.0


def test_ingestion_rejects_undeclared_facet_value(fcai_profile):
    doc = SourceDocument("x.md", "x", "raw", "# T\nbody", {
        "title": "t", "tenant": "fcai", "product": "fcai-cloud", "plan": "platinum",
        "doc_type": "plan", "version": "1", "status": "published", "visibility": "internal"})
    with pytest.raises(IngestionError, match="platinum"):
        validate_metadata(doc, fcai_profile)


def test_memory_filter_dsl():
    meta = {"plan": "pro", "status": "published"}
    assert matches(meta, {"plan": {"$in": ["pro", "all"]}, "status": "published"})
    assert not matches(meta, {"plan": {"$nin": ["pro"]}})


def test_ingest_index_incremental_and_contract(tmp_path, hr_profile):
    settings = make_settings(tmp_path)
    ingest(settings, hr_profile)
    index = InMemoryIndex(settings, hr_profile, HashEmbeddings())
    first = index_chunks(settings, hr_profile, index)
    assert len(first["new"]) == 6
    second = index_chunks(settings, hr_profile, InMemoryIndex(settings, hr_profile, HashEmbeddings()))
    assert len(second["unchanged"]) == 6 and not second["new"]

    # The startup contract catches an index/profile mismatch.
    from conftest import build_pipeline
    pipeline = build_pipeline(hr_profile, settings, None, None, None)
    pipeline.index = index
    pipeline.check_index_contract()
    hr_profile.facet("country").values.pop("br")
    with pytest.raises(IndexContractError, match="br"):
        pipeline.check_index_contract()
