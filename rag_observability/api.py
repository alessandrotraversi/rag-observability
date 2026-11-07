"""HTTP API over the shared pipeline.

    uvicorn rag_observability.api:app --reload

`create_app()` takes an optional container and scope resolver so you can mount the
pipeline inside your own service and derive the scope from your own authentication.
"""

from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from rag_observability.bootstrap import Container, build_container
from rag_observability.core.errors import ScopeError
from rag_observability.core.results import RagPipelineResult

ScopeResolver = Callable[[Request], dict[str, Any]]
SCOPE_HEADER_PREFIX = "x-rag-scope-"


class ChatRequest(BaseModel):
    question: str
    debug: bool = False
    use_rerank: bool = True


def no_scope(request: Request) -> dict[str, Any]:
    """Default: only the profile's enforced filters apply."""
    return {}


def header_scope(request: Request) -> dict[str, Any]:
    """X-RAG-Scope-<field>: <value>. ONLY behind a gateway that sets them from auth."""
    return {
        name[len(SCOPE_HEADER_PREFIX):].replace("-", "_"): value
        for name, value in request.headers.items()
        if name.lower().startswith(SCOPE_HEADER_PREFIX)
    }


def create_app(
    container: Container | None = None, scope_resolver: ScopeResolver | None = None
) -> FastAPI:
    container = container or build_container()
    if scope_resolver is None:
        scope_resolver = header_scope if container.settings.api_scope_from_headers else no_scope
    pipeline = container.pipeline

    app = FastAPI(title=f"RAG API — {container.profile.name}")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "profile": container.profile.name}

    @app.post("/chat", response_model_exclude_none=True)
    def chat(body: ChatRequest, request: Request) -> RagPipelineResult:
        question = body.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="question must not be empty")
        try:
            return pipeline.run(
                question,
                scope=scope_resolver(request),
                use_rerank=body.use_rerank,
                include_debug=body.debug,
            )
        except ScopeError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except Exception:
            # The pipeline already logged request_id, error type and message.
            raise HTTPException(status_code=500, detail="RAG pipeline failed.")

    return app


def __getattr__(name: str):
    # `uvicorn rag_observability.api:app` builds the app lazily, so importing this
    # module (tests, embedding) does not connect to anything.
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
