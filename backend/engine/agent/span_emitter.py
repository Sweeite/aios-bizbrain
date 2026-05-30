from engine.spine.types import Span


class SpanEmitter:
    def __init__(self) -> None:
        self._spans: list[Span] = []

    def emit(self, span: Span) -> None:
        self._spans.append(span)

    def spans(self) -> list[Span]:
        return list(self._spans)
