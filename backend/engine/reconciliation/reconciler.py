from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReconciliationResult:
    source_system: str
    checked: int
    misses: list[str]
    cursor: str
    gap_triggered: bool


class Reconciler:
    def __init__(self, gap_threshold: int = 1) -> None:
        self._gap_threshold = gap_threshold
        self._cursors: dict[str, str] = {}

    def reconcile(
        self,
        source_system: str,
        known_event_ids: set[str],
        available_event_ids: list[str],
    ) -> ReconciliationResult:
        misses = [eid for eid in available_event_ids if eid not in known_event_ids]
        cursor = available_event_ids[-1] if available_event_ids else ""
        self._cursors[source_system] = cursor
        return ReconciliationResult(
            source_system=source_system,
            checked=len(available_event_ids),
            misses=misses,
            cursor=cursor,
            gap_triggered=len(misses) >= self._gap_threshold,
        )

    def get_cursor(self, source_system: str) -> str | None:
        return self._cursors.get(source_system)
