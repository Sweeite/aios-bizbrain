"""
Slice 10: Consolidation + reconciliation — reconciliation half.
"""
import pytest


# ---------------------------------------------------------------------------
# Reconciler
# ---------------------------------------------------------------------------

class TestReconciler:
    def test_no_misses_when_all_known(self):
        from engine.reconciliation.reconciler import Reconciler

        result = Reconciler().reconcile("hubspot", {"A", "B", "C"}, ["A", "B", "C"])

        assert result.misses == []

    def test_detects_missed_events(self):
        from engine.reconciliation.reconciler import Reconciler

        result = Reconciler().reconcile("hubspot", {"A", "B"}, ["A", "B", "C", "D"])

        assert sorted(result.misses) == ["C", "D"]

    def test_cursor_advances_to_last_available(self):
        from engine.reconciliation.reconciler import Reconciler

        r = Reconciler()
        r.reconcile("hubspot", set(), ["A", "B", "C"])

        assert r.get_cursor("hubspot") == "C"

    def test_cursor_starts_none(self):
        from engine.reconciliation.reconciler import Reconciler

        assert Reconciler().get_cursor("hubspot") is None

    def test_gap_triggered_when_misses_meet_threshold(self):
        from engine.reconciliation.reconciler import Reconciler

        result = Reconciler(gap_threshold=2).reconcile("hubspot", {"A"}, ["A", "B", "C"])

        assert result.gap_triggered is True

    def test_gap_not_triggered_below_threshold(self):
        from engine.reconciliation.reconciler import Reconciler

        result = Reconciler(gap_threshold=2).reconcile("hubspot", {"A", "B"}, ["A", "B", "C"])

        assert result.gap_triggered is False


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

class TestReconciliationTask:
    def test_task_registered_with_celery_app(self):
        from engine.worker.celery_app import celery_app
        from engine.worker import tasks  # noqa: F401

        assert "engine.worker.tasks.reconciliation.reconcile_connector" in celery_app.tasks

    def test_task_returns_misses_and_cursor(self):
        from engine.worker.tasks.reconciliation import reconcile_connector

        result = reconcile_connector.apply(args=["hubspot", ["A", "B"], ["A", "B", "C"]])

        assert result.successful()
        assert result.result["misses"] == ["C"]
        assert result.result["cursor"] == "C"
        assert result.result["gap_triggered"] is True
