"""Hashes and the index manifest (what was indexed, with which chunk ids)."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_VERSION = "rag-observability-v1"


def document_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"version": MANIFEST_VERSION, "sources": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(sources: dict, path: Path, fingerprint: dict) -> None:
    manifest = {
        "version": MANIFEST_VERSION,
        "indexed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # Which embedding model built the vectors: changing it forces a rebuild.
        "fingerprint": fingerprint,
        "sources": sources,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
