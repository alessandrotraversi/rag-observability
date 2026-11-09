"""Source loaders: turn files into (source_name, raw_text, body, metadata).

Built-in: "markdown" (YAML front matter + Markdown body). Other formats plug in by
a dotted path in the profile (ingestion.loader: "pkg.module:load"), with the same
signature as `load_markdown_documents`.
"""

from dataclasses import dataclass
from typing import Any, Callable

import frontmatter

from rag_observability.core.errors import IngestionError
from rag_observability.domain.profile import DomainProfile


@dataclass
class SourceDocument:
    name: str  # stable identifier (file name), used as source_file
    stem: str  # used to build chunk ids
    raw: str  # the full raw file, hashed for incremental indexing
    body: str
    metadata: dict[str, Any]


def load_markdown_documents(profile: DomainProfile) -> list[SourceDocument]:
    directory = profile.source_dir
    if not directory.is_dir():
        raise IngestionError(f"knowledge base directory not found: {directory}")
    paths = sorted(directory.glob(profile.ingestion.glob))
    if not paths:
        raise IngestionError(f"no documents matching {profile.ingestion.glob} in {directory}")

    documents = []
    for path in paths:
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            raise IngestionError(f"{path.name}: file is empty")
        post = frontmatter.loads(raw.strip())
        if not post.content.strip():
            raise IngestionError(f"{path.name}: document body is empty")
        documents.append(
            SourceDocument(
                name=path.name, stem=path.stem, raw=raw,
                body=post.content, metadata=dict(post.metadata),
            )
        )
    return documents


Loader = Callable[[DomainProfile], list[SourceDocument]]
BUILTIN_LOADERS: dict[str, Loader] = {"markdown": load_markdown_documents}
