from __future__ import annotations

from engine.spine.types import Run


class InMemoryRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}

    def save(self, run: Run) -> None:
        self._runs[run.run_id] = run

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)
