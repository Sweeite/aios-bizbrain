from __future__ import annotations

from engine.spine.types import Span


class SpanEmitter:
    def __init__(self, store=None) -> None:
        self._spans: list[Span] = []
        self._store = store

    def emit(self, span: Span) -> None:
        self._spans.append(span)
        if self._store is not None:
            self._store.save(span)

    def spans(self) -> list[Span]:
        return list(self._spans)
