"""Isolated retrieval, no chat model: see what the index returns for a query.

    python -m rag_observability.cli.retrieve "question" [--top-k 30] [--filter field=value ...]
"""

import argparse
import sys

from rag_observability.bootstrap import build_embeddings_for, build_index
from rag_observability.core.errors import RagError
from rag_observability.core.filters import format_filters
from rag_observability.domain.profile import load_profile
from rag_observability.settings import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Isolated retrieval test.")
    parser.add_argument("query", nargs="?")
    parser.add_argument("--top-k", type=int, default=30)
    parser.add_argument("--filter", action="append", default=[], metavar="FIELD=VALUE",
                        help="repeatable; comma-separated values become $in")
    parser.add_argument("--preview", type=int, default=500)
    args = parser.parse_args()

    query = args.query or input("Question: ").strip()
    if not query:
        print("No question provided.", file=sys.stderr)
        raise SystemExit(1)
    filters = {}
    for pair in args.filter:
        key, _, value = pair.partition("=")
        values = [v for v in value.split(",") if v]
        filters[key] = {"$in": values} if len(values) > 1 else value

    try:
        settings = load_settings()
        profile = load_profile(settings.profile_path)
        index = build_index(settings, profile, build_embeddings_for(settings))
        results = index.search(query, k=args.top_k, filters=filters or None)
    except RagError as exc:
        print(f"Retrieval failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Query: {query}\nTop K: {args.top_k}\nFilters: {format_filters(filters)}")
    print(f"Total results: {len(results)}\n")
    for rank, (document, score) in enumerate(results, start=1):
        m = document.metadata
        print(f"{rank}. Score: {score:.3f} | {m.get('chunk_id')} | {m.get('source_file')} | {m.get('section')}")
        for line in document.page_content[: args.preview].splitlines():
            print(f"     {line}")
        print()


if __name__ == "__main__":
    main()
