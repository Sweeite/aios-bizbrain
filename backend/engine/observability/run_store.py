from __future__ import annotations

from engine.spine.types import Run


class InMemoryRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}

    def save(self, run: Run) -> None:
        self._runs[run.run_id] = run

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def list(self, scope_entity_ref: str | None = None) -> list[Run]:
        runs = list(self._runs.values())
        if scope_entity_ref is not None:
            runs = [r for r in runs if r.scope.entity_ref == scope_entity_ref]
        return sorted(runs, key=lambda r: r.started_at, reverse=True)
