from __future__ import annotations

from engine.ingestion.memory_writer import MemoryWriter
from engine.spine.types import BusinessEvent, MemoryStore, Scope, ScopeLevel


class ScopeViolationError(Exception):
    pass


class ClientProfileService:
    def __init__(
        self,
        clients: list[dict],
        memory_writer: MemoryWriter,
        events: list[BusinessEvent],
    ) -> None:
        self._clients: dict[str, dict] = {c["id"]: c for c in clients}
        self._memory = memory_writer
        self._events_by_entity: dict[str, list[BusinessEvent]] = {}
        for event in events:
            for entity_ref in event.entities:
                self._events_by_entity.setdefault(entity_ref, []).append(event)

    def list_clients(self, caller_scope: Scope) -> list[dict]:
        clients = list(self._clients.values())
        if caller_scope.level == ScopeLevel.entity:
            clients = [c for c in clients if c["id"] == caller_scope.entity_ref]
        return [
            {
                "id": c["id"],
                "name": c["name"],
                **self._live_deal_summary(c["id"]),
            }
            for c in clients
        ]

    def get_profile(self, client_id: str, caller_scope: Scope) -> dict | None:
        if client_id not in self._clients:
            return None
        if not _scope_allows(caller_scope, client_id):
            raise ScopeViolationError(f"scope {caller_scope.level} cannot access {client_id}")

        client = self._clients[client_id]
        org_scope = Scope(level=ScopeLevel.org)
        episodes = self._memory.recall(client_id, org_scope)

        return {
            "id": client_id,
            "name": client["name"],
            "brain_understanding": {
                "entity_facts": [
                    _fmt_record(r) for r in episodes if r.store == MemoryStore.entity
                ],
                "episodic_history": [
                    _fmt_record(r) for r in episodes if r.store == MemoryStore.episodic
                ],
            },
            "live_status": self._live_status(client_id),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _events_for(self, client_id: str) -> list[BusinessEvent]:
        return self._events_by_entity.get(client_id, [])

    def _live_deal_summary(self, client_id: str) -> dict:
        for event in self._events_for(client_id):
            if event.source_system == "hubspot" and event.event_type == "deal.stage_changed":
                return {
                    "deal_stage": event.body.get("to_stage"),
                    "deal_name": event.body.get("deal_name"),
                }
        return {"deal_stage": None, "deal_name": None}

    def _live_status(self, client_id: str) -> dict:
        deal = None
        budget = None
        open_tasks: list[dict] = []
        invoices: list[dict] = []

        for event in self._events_for(client_id):
            src = event.source_system
            etype = event.event_type

            if src == "hubspot" and etype == "deal.stage_changed":
                deal = {
                    "deal_name": event.body.get("deal_name"),
                    "stage": event.body.get("to_stage"),
                    "days_in_stage": event.body.get("days_in_stage"),
                }

            elif src == "harvest":
                budget = {
                    "engagement": event.body.get("engagement"),
                    "budget_usd": event.body.get("budget_usd"),
                    "spent_usd": event.body.get("spent_usd"),
                    "event_type": etype,
                }

            elif src == "asana":
                open_tasks.append({
                    "task_name": event.body.get("task_name"),
                    "event_type": etype,
                    "project": event.body.get("project"),
                })

            elif src == "quickbooks":
                invoices.append({
                    "invoice_number": event.body.get("invoice_number"),
                    "amount_usd": event.body.get("amount_usd"),
                    "event_type": etype,
                })

        return {"deal": deal, "budget": budget, "open_tasks": open_tasks, "invoices": invoices}


def _scope_allows(caller_scope: Scope, client_id: str) -> bool:
    if caller_scope.level == ScopeLevel.org:
        return True
    if caller_scope.level == ScopeLevel.entity:
        return caller_scope.entity_ref == client_id
    return False


def _fmt_record(record) -> dict:
    return {
        "store": record.store.value,
        "payload": record.payload,
        "confidence": record.confidence.value,
        "as_of": record.temporal_validity.get("as_of"),
        "source": record.provenance,
    }
