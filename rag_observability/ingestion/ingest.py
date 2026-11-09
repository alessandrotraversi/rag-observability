"""CLI: load, validate and chunk the profile's knowledge base into chunks.jsonl.

    python -m rag_observability.ingestion.ingest [--no-context-header]
"""

import argparse
import json
import sys

from rag_observability.core.errors import RagError
from rag_observability.domain.profile import DomainProfile, load_profile
from rag_observability.ingestion.chunking import chunk_document, chunks_path, validate_metadata
from rag_observability.ingestion.loaders import BUILTIN_LOADERS
from rag_observability.providers.registry import resolve
from rag_observability.settings import Settings, load_settings


def ingest(settings: Settings, profile: DomainProfile, context_header: bool = True) -> list[dict]:
    loader = resolve("loader", profile.ingestion.loader, BUILTIN_LOADERS)
    documents = loader(profile)
    for document in documents:
        validate_metadata(document, profile)
    chunks = [c for d in documents for c in chunk_document(d, profile, context_header)]

    output = chunks_path(settings.data_dir, profile)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    print(f"Profile: {profile.name}")
    print(f"Loaded documents: {len(documents)}")
    print(f"Context header: {'enabled' if context_header else 'disabled'}")
    print(f"Generated chunks: {len(chunks)} -> {output}")
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and chunk the knowledge base.")
    parser.add_argument("--no-context-header", action="store_true")
    args = parser.parse_args()
    try:
        settings = load_settings()
        ingest(settings, load_profile(settings.profile_path), not args.no_context_header)
    except RagError as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
