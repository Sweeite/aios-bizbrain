from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_run_store, get_span_store
from engine.observability.run_store import InMemoryRunStore
from engine.observability.span_store import InMemorySpanStore

router = APIRouter(tags=["traces"])


@router.get("/runs/{run_id}/trace")
def get_trace(
    run_id: str,
    span_store: InMemorySpanStore = Depends(get_span_store),
    run_store: InMemoryRunStore = Depends(get_run_store),
):
    run = run_store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
    spans = sorted(span_store.get_by_run(run_id), key=lambda s: s.started_at)
    return {"run_id": run_id, "spans": [s.model_dump(mode="json") for s in spans]}
