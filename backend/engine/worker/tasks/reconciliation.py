from engine.reconciliation.reconciler import Reconciler
from engine.worker.celery_app import celery_app


@celery_app.task(name="engine.worker.tasks.reconciliation.reconcile_connector")
def reconcile_connector(
    source_system: str,
    known_event_ids: list[str],
    available_event_ids: list[str],
) -> dict:
    result = Reconciler().reconcile(source_system, set(known_event_ids), available_event_ids)
    return {
        "misses": result.misses,
        "gap_triggered": result.gap_triggered,
        "cursor": result.cursor,
    }
