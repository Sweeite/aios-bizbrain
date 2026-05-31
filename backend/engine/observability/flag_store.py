from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass, field


@dataclass
class FlaggedItem:
    type: str
    entity_ref: str
    label: str
    since: datetime


_SEED: list[FlaggedItem] = [
    FlaggedItem(
        type="stalled_deal",
        entity_ref="client-meridian-001",
        label="Meridian Capital — proposal sent 18 days ago, no response",
        since=datetime(2026, 5, 13, 9, 0, tzinfo=timezone.utc),
    ),
    FlaggedItem(
        type="overdue_invoice",
        entity_ref="client-vertex-002",
        label="Vertex Partners — invoice #2043 overdue by 12 days",
        since=datetime(2026, 5, 19, 0, 0, tzinfo=timezone.utc),
    ),
]


class FlagStore:
    def __init__(self) -> None:
        self._items: list[FlaggedItem] = list(_SEED)

    def flag(self, item: FlaggedItem) -> None:
        self._items.append(item)

    def list_flags(self, entity_ref: str | None = None) -> list[FlaggedItem]:
        if entity_ref is None:
            return list(self._items)
        return [f for f in self._items if f.entity_ref == entity_ref]


_store: FlagStore | None = None


def get_flag_store() -> FlagStore:
    global _store
    if _store is None:
        _store = FlagStore()
    return _store
