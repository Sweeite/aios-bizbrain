from __future__ import annotations

from engine.spine.types import Span


class InMemorySpanStore:
    def __init__(self) -> None:
        self._spans: list[Span] = []

    def save(self, span: Span) -> None:
        self._spans.append(span)

    def get_by_run(self, run_id: str) -> list[Span]:
        return [s for s in self._spans if s.run_id == run_id]
