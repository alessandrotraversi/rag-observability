"""Terminal chat over the shared pipeline.

    python -m rag_observability.cli.chat [--debug] [--show-prompt] [--no-rerank]
                                         [--scope field=value ...]
"""

import argparse
import sys

from langchain_core.prompt_values import PromptValue

from rag_observability.bootstrap import build_container
from rag_observability.core.errors import RagError
from rag_observability.core.filters import format_filters
from rag_observability.core.results import RagDebug, Source


def print_prompt(label: str, prompt_value: PromptValue) -> None:
    print(f"\n--- {label} ---")
    for message in prompt_value.to_messages():
        print(f"\n[{message.type}]\n{message.text}")
    print(f"\n--- End of {label.lower()} ---")


def _ms(value: float | None) -> str:
    return f"{value} ms" if value is not None else "-"


def print_debug(debug: RagDebug) -> None:
    if debug.policy:
        p = debug.policy
        print("\n--- Policy ---")
        print(f"Allowed: {p.allowed} ({p.reason}) | model: {p.model} | scope: {p.scope}")
        print(f"Budget: USD {p.monthly_budget_usd} | month spend: USD {p.current_month_spend_usd}")
    if debug.query_plan:
        q = debug.query_plan
        print("\n--- Query plan ---")
        print(f"Normalized question: {q.normalized_question}")
        for facet, values in q.facets.items():
            print(f"{facet}: {', '.join(values) or None}")
        print(f"Exact terms: {', '.join(q.exact_terms) or None}")
        print(f"Needs clarification: {q.needs_clarification}")
        print(f"Search query: {q.search_query}")
        print(f"Filters: {format_filters(q.filters)}")
        if not q.needs_clarification:
            print("\n--- Retrieved chunks ---")
            for c in debug.retrieved_chunks:
                print(f"{c.rank}. [{c.score:.3f}] {c.chunk_id} | {c.source_file} | {c.section}")
            print(f"Selected: {', '.join(debug.selected_chunk_ids) or None}")
    t = debug.timings
    print("\n--- Pipeline ---")
    print(f"Request ID: {debug.request_id} | profile: {debug.profile}")
    print(
        f"Timings: plan {_ms(t.query_planning_ms)} | retrieval {_ms(t.retrieval_ms)} | "
        f"rerank {_ms(t.reranking_ms)} | answer {_ms(t.answer_generation_ms)} | total {_ms(t.total_ms)}"
    )
    for u in debug.model_usage:
        print(f"Usage: {u.model}: {u.input_tokens} in + {u.output_tokens} out "
              f"= {u.total_tokens} tokens (~USD {u.estimated_cost_usd})")


def print_sources(sources: list[Source]) -> None:
    print("\nSources:")
    if not sources:
        print("No sources.")
    for rank, s in enumerate(sources, start=1):
        extra = "".join(f" | {k}: {v}" for k, v in s.attributes.items())
        print(f"{rank}. {s.source_file} | {s.title}" + (f" | {s.section}" if s.section else "") + extra)


def parse_scope(pairs: list[str]) -> dict[str, str]:
    scope = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise SystemExit(f"--scope expects field=value, got '{pair}'")
        scope[key] = value
    return scope


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG chat.")
    parser.add_argument("--show-prompt", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument("--scope", action="append", default=[], metavar="FIELD=VALUE")
    args = parser.parse_args()
    scope = parse_scope(args.scope)

    try:
        container = build_container()
    except RagError as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print(f"RAG chat started — profile '{container.profile.name}'. Type 'exit' to quit.")
    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue
        try:
            result = container.pipeline.run(
                question, scope=scope, use_rerank=not args.no_rerank,
                include_debug=args.debug,
                on_prompt=print_prompt if args.show_prompt else None,
            )
        except RagError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            continue
        if result.debug:
            print_debug(result.debug)
        print(f"\nAnswer:\n{result.answer}")
        if not result.needs_clarification and not result.policy_blocked:
            print_sources(result.sources)


if __name__ == "__main__":
    main()
