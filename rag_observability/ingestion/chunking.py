"""Structure-aware chunking driven by the profile.

Headings first (MarkdownHeaderTextSplitter), then size (RecursiveCharacterTextSplitter),
then a context header prepended to each chunk so metadata reaches the embedding.
"""

from pathlib import Path

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from rag_observability.core.errors import IngestionError
from rag_observability.domain.profile import DomainProfile
from rag_observability.ingestion.loaders import SourceDocument
from rag_observability.ingestion.manifest import document_hash


def chunks_path(data_dir: Path, profile: DomainProfile) -> Path:
    return data_dir / profile.collection / "chunks.jsonl"


def manifest_path(data_dir: Path, profile: DomainProfile) -> Path:
    return data_dir / profile.collection / "index_manifest.json"


def validate_metadata(document: SourceDocument, profile: DomainProfile) -> None:
    missing = [k for k in profile.ingestion.required_metadata if k not in document.metadata]
    if missing:
        raise IngestionError(f"{document.name}: missing required metadata: {', '.join(missing)}")
    for facet in profile.facets:
        value = document.metadata.get(facet.metadata_field)
        allowed = set(facet.values) | ({facet.wildcard} if facet.wildcard else set())
        if value is not None and str(value) not in allowed:
            # Caught here, at ingestion, instead of vanishing from filtered searches.
            raise IngestionError(
                f"{document.name}: {facet.metadata_field}='{value}' is not a declared "
                f"value of facet '{facet.name}' ({', '.join(sorted(allowed))})"
            )


def _section_of(header_metadata: dict, levels: int) -> str | None:
    for level in range(levels, 0, -1):
        if header_metadata.get(f"h{level}"):
            return header_metadata[f"h{level}"]
    return None


def build_context_header(metadata: dict, profile: DomainProfile) -> str:
    return "\n".join(
        f"{item.label}: {metadata[item.field]}"
        for item in profile.ingestion.context_header
        if metadata.get(item.field)
    )


def chunk_document(
    document: SourceDocument, profile: DomainProfile, context_header: bool = True
) -> list[dict]:
    cfg = profile.ingestion
    headers = [(marker, f"h{len(marker)}") for marker in cfg.split_headers]
    sections = MarkdownHeaderTextSplitter(headers_to_split_on=headers).split_text(document.body)
    pieces = RecursiveCharacterTextSplitter(
        chunk_size=cfg.chunk_size, chunk_overlap=cfg.chunk_overlap
    ).split_documents(sections)

    digest = document_hash(document.raw)
    chunks = []
    for index, piece in enumerate(pieces):
        metadata = {
            # Metadata values must be JSON-serializable primitives for every store.
            **{k: (v if isinstance(v, (str, int, float, bool)) or v is None else str(v))
               for k, v in document.metadata.items()},
            "document_hash": digest,
            # Deterministic: same file + same content + same position = same id.
            "chunk_id": f"{document.stem}-{digest[:12]}-{index:04d}",
            "source_file": document.name,
            "chunk_index": index,
            "section": _section_of(piece.metadata, len(cfg.split_headers)),
        }
        content = piece.page_content
        if context_header:
            header = build_context_header(metadata, profile)
            content = f"{header}\n\n{content}" if header else content
        metadata["content_length"] = len(content)
        chunks.append({"content": content, "metadata": metadata})
    return chunks
