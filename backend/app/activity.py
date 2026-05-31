from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.deps import get_run_store, get_span_store
from engine.observability.run_store import InMemoryRunStore
from engine.observability.span_store import InMemorySpanStore
from engine.spine.types import SpanOp

router = APIRouter(tags=["activity"])


def _trigger_type(initiated_by: str) -> str:
    return "human-directed" if initiated_by.startswith("user") else "proactive"


def _outcome(status: str) -> str:
    return "completed" if status == "done" else status


_INFRA_ACTORS = {"orchestrator", "memory-writer"}


def _primary_agent(run_id: str, span_store: InMemorySpanStore) -> str | None:
    spans = span_store.get_by_run(run_id)
    agent_spans = [
        s for s in spans
        if s.op == SpanOp.reason and s.actor not in _INFRA_ACTORS
    ]
    if agent_spans:
        return sorted(agent_spans, key=lambda s: s.started_at)[0].actor
    return None


@router.get("/activity")
def list_activity(
    scope: str | None = Query(default=None),
    run_store: InMemoryRunStore = Depends(get_run_store),
    span_store: InMemorySpanStore = Depends(get_span_store),
) -> list[dict[str, Any]]:
    runs = run_store.list(scope_entity_ref=scope)
    return [
        {
            "run_id": r.run_id,
            "trigger": r.initiated_by,
            "trigger_type": _trigger_type(r.initiated_by),
            "primary_agent": _primary_agent(r.run_id, span_store),
            "outcome": _outcome(r.status),
            "started_at": r.started_at.isoformat(),
        }
        for r in runs
    ]
