"""CLI: embed and index chunks into the configured VectorIndex, only what changed.

    python -m rag_observability.ingestion.index [--force]
"""

import argparse
import json
import sys

from langchain_core.documents import Document

from rag_observability.bootstrap import build_embeddings_for, build_index
from rag_observability.core.errors import IndexingError, RagError
from rag_observability.core.ports import VectorIndex
from rag_observability.domain.profile import DomainProfile, load_profile
from rag_observability.ingestion.chunking import chunks_path, manifest_path
from rag_observability.ingestion.manifest import load_manifest, save_manifest
from rag_observability.settings import Settings, load_settings

REQUIRED_CHUNK_FIELDS = ("chunk_id", "source_file", "document_hash")


def load_chunks(settings: Settings, profile: DomainProfile) -> list[Document]:
    path = chunks_path(settings.data_dir, profile)
    if not path.exists():
        raise IndexingError(f"chunks file not found: {path} (run ingest first)")
    documents = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise IndexingError(f"line {number}: invalid JSON ({exc})") from exc
        metadata = record.get("metadata") or {}
        if not record.get("content"):
            raise IndexingError(f"line {number}: missing content")
        for field in REQUIRED_CHUNK_FIELDS:
            if not metadata.get(field):
                raise IndexingError(f"line {number}: missing metadata.{field}")
        documents.append(Document(page_content=record["content"], metadata=metadata))
    if not documents:
        raise IndexingError(f"no chunks found in {path}")
    return documents


def group_by_source(documents: list[Document]) -> dict[str, list[Document]]:
    grouped: dict[str, list[Document]] = {}
    for document in documents:
        grouped.setdefault(document.metadata["source_file"], []).append(document)
    return grouped


def classify_sources(grouped: dict[str, list[Document]], indexed: dict) -> dict[str, list[str]]:
    changes = {"new": [], "changed": [], "unchanged": [], "removed": []}
    for source, docs in grouped.items():
        previous = indexed.get(source)
        if previous is None:
            changes["new"].append(source)
        elif previous["document_hash"] != docs[0].metadata["document_hash"]:
            changes["changed"].append(source)
        else:
            changes["unchanged"].append(source)
    changes["removed"] = [s for s in indexed if s not in grouped]
    return changes


def index_chunks(
    settings: Settings, profile: DomainProfile, index: VectorIndex, force: bool = False
) -> dict[str, list[str]]:
    documents = load_chunks(settings, profile)
    grouped = group_by_source(documents)
    manifest_file = manifest_path(settings.data_dir, profile)
    manifest = load_manifest(manifest_file)
    fingerprint = {"embedding_provider": settings.embedding_provider,
                   "embedding_model": settings.embedding_model,
                   "vector_store": settings.vector_store}
    indexed = manifest.get("sources", {})

    # Unknown state (no manifest, no collection, other embedding model): rebuild.
    rebuild = not indexed or not index.exists() or manifest.get("fingerprint") != fingerprint
    if rebuild:
        indexed = {}
        index.reset()

    changes = classify_sources(grouped, indexed)
    if force:
        delete_ids = [cid for entry in indexed.values() for cid in entry["chunk_ids"]]
        to_index = list(grouped)
    else:
        delete_ids = [
            cid for source in changes["removed"] + changes["changed"]
            for cid in indexed[source]["chunk_ids"]
        ]
        to_index = changes["new"] + changes["changed"]

    docs_to_index = [d for source in to_index for d in grouped[source]]
    index.delete(delete_ids)
    index.upsert(docs_to_index, [d.metadata["chunk_id"] for d in docs_to_index])

    keep = profile.ingestion.required_metadata
    save_manifest(
        {
            source: {
                "document_hash": docs[0].metadata["document_hash"],
                **{k: docs[0].metadata.get(k) for k in keep},
                "chunk_ids": [d.metadata["chunk_id"] for d in docs],
            }
            for source, docs in grouped.items()
        },
        manifest_file,
        fingerprint,
    )
    print(f"Profile: {profile.name} | collection: {profile.collection} | store: {settings.vector_store}")
    print(f"Rebuild: {rebuild}")
    for kind in ("new", "changed", "removed", "unchanged"):
        print(f"{kind.capitalize()} sources: {len(changes[kind])}")
    print(f"Deleted chunks: {len(delete_ids)}")
    print(f"Indexed chunks: {len(docs_to_index)}")
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Index chunks, reindexing only what changed.")
    parser.add_argument("--force", action="store_true", help="reindex every current chunk")
    args = parser.parse_args()
    try:
        settings = load_settings()
        profile = load_profile(settings.profile_path)
        index = build_index(settings, profile, build_embeddings_for(settings))
        index_chunks(settings, profile, index, force=args.force)
    except RagError as exc:
        print(f"Indexing failed: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
