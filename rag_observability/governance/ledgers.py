"""UsageLedger adapters. Production should plug a transactional store (SQL, Redis).

- JsonlUsageLedger: one JSON line per run, read back in full. Teaching/dev only:
  no cross-process coordination and O(n) reads, exactly like upstream.
- InMemoryUsageLedger: tests and ephemeral demos.
- NullUsageLedger: records nothing, spend is always 0 (budget effectively off).
"""

import json
import threading
from datetime import datetime
from pathlib import Path

from rag_observability.governance.models import UsageRecord


def _matches(record: dict, since: datetime, feature: str, scope: dict[str, str]) -> bool:
    if record.get("feature") != feature:
        return False
    recorded_scope = record.get("scope") or {}
    if any(recorded_scope.get(k) != v for k, v in scope.items()):
        return False
    try:
        return datetime.fromisoformat(record["timestamp"]) >= since
    except (KeyError, ValueError):
        return False


class JsonlUsageLedger:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def record(self, record: UsageRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record.model_dump(), ensure_ascii=False) + "\n"
        with self._lock, self.path.open("a", encoding="utf-8") as ledger:
            ledger.write(line)

    def spend_since(self, since: datetime, feature: str, scope: dict[str, str]) -> float:
        if not self.path.exists():
            return 0.0
        total = 0.0
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if _matches(record, since, feature, scope):
                total += float(record.get("estimated_cost_usd", 0.0))
        return round(total, 6)


class InMemoryUsageLedger:
    def __init__(self) -> None:
        self.records: list[UsageRecord] = []

    def record(self, record: UsageRecord) -> None:
        self.records.append(record)

    def spend_since(self, since: datetime, feature: str, scope: dict[str, str]) -> float:
        total = sum(
            r.estimated_cost_usd
            for r in self.records
            if _matches(r.model_dump(), since, feature, scope)
        )
        return round(total, 6)


class NullUsageLedger:
    def record(self, record: UsageRecord) -> None:
        return None

    def spend_since(self, since: datetime, feature: str, scope: dict[str, str]) -> float:
        return 0.0
