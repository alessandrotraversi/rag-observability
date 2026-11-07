"""Check that a deployment holds together, without spending tokens.

    python -m rag_observability.cli.doctor

Settings, observability policy, profile, pricing coverage, provider packages,
vector store reachability and the index/profile contract.
"""

import importlib.util

from rag_observability.core.errors import RagError

PROVIDER_PACKAGES = {
    "openai": "langchain_openai", "azure_openai": "langchain_openai",
    "anthropic": "langchain_anthropic", "google_genai": "langchain_google_genai",
    "google_vertexai": "langchain_google_vertexai", "bedrock": "langchain_aws",
    "bedrock_converse": "langchain_aws", "ollama": "langchain_ollama",
    "mistralai": "langchain_mistralai", "groq": "langchain_groq",
    "huggingface": "langchain_huggingface", "cohere": "langchain_cohere",
}


def check(label: str, fn) -> bool:
    try:
        detail = fn()
        print(f"[ok]   {label}" + (f" — {detail}" if detail else ""))
        return True
    except (RagError, ImportError, ValueError, OSError) as exc:
        print(f"[fail] {label} — {exc}")
        return False
    except Exception as exc:  # connectivity errors vary per driver
        print(f"[fail] {label} — {type(exc).__name__}: {exc}")
        return False


def main() -> None:
    from rag_observability.bootstrap import build_embeddings_for, build_index, build_ledger, build_policy
    from rag_observability.domain.profile import load_profile
    from rag_observability.governance.pricing import load_price_table
    from rag_observability.observability.tracing import validate_observability_policy
    from rag_observability.settings import load_settings

    ok = True
    state: dict = {}

    def settings():
        state["settings"] = load_settings()
        s = state["settings"]
        return f"env={s.app_env} llm={s.llm_provider}:{s.llm_model} embeddings={s.embedding_provider}:{s.embedding_model} store={s.vector_store}"

    if not check("settings", settings):
        raise SystemExit(1)
    s = state["settings"]

    ok &= check("observability policy", lambda: validate_observability_policy(s))

    def profile():
        state["profile"] = load_profile(s.profile_path)
        p = state["profile"]
        return f"{p.name}: {len(p.facets)} facets, collection '{p.collection}'"

    ok &= check("domain profile", profile)
    ok &= check("pricing + governance", lambda: build_policy(s, load_price_table(s.pricing_path), build_ledger(s)) and
                f"allowed={s.allowed_models}")

    for kind, provider in (("chat", s.llm_provider), ("embedding", s.embedding_provider)):
        package = PROVIDER_PACKAGES.get(provider)
        if package:
            def has(package=package):
                if importlib.util.find_spec(package) is None:
                    raise ImportError(f"pip install {package.replace('_', '-')}")
                return package
            ok &= check(f"{kind} provider package", has)

    if "profile" in state:
        def store():
            index = build_index(s, state["profile"], build_embeddings_for(s))
            state["index"] = index
            return f"{index.count()} chunks"
        store_ok = check("vector store", store)
        if store_ok and not state["index"].count():
            print("[fail] index — collection is empty: run rag_observability.ingestion.ingest "
                  "and rag_observability.ingestion.index")
            ok = False
        elif store_ok:
            def contract():
                profile, index = state["profile"], state["index"]
                for facet in profile.facets:
                    unknown = index.distinct_values(facet.metadata_field) - set(facet.values) - {facet.wildcard}
                    if unknown:
                        raise ValueError(f"{facet.metadata_field}: undeclared values {sorted(unknown)}")
                return "index values match the facets"
            ok &= check("index/profile contract", contract)
        else:
            ok = False

    print("\nAll checks passed." if ok else "\nSome checks failed.")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
