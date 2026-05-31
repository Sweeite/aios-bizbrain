"""
Slice 15 proving path — Client Profiles API.
Runs without a live server; exercises the service layer directly.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from packs.consulting.clients import CLIENTS, KNOWN_CLIENT_IDS
from packs.consulting.connectors.registry import ConnectorRegistry
from engine.clients.profile_service import ClientProfileService, ScopeViolationError
from engine.ingestion.entity_resolver import EntityResolver
from engine.ingestion.memory_writer import MemoryWriter
from engine.spine.types import Scope, ScopeLevel

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

def check(label: str, condition: bool) -> None:
    print(f"  [{PASS if condition else FAIL}] {label}")
    if not condition:
        sys.exit(1)


def build_service() -> ClientProfileService:
    events = ConnectorRegistry().pull_all()
    resolver = EntityResolver({cid: cid for cid in KNOWN_CLIENT_IDS})
    writer = MemoryWriter()
    for event in events:
        resolved = resolver.resolve(event)
        writer.write(resolved)
    return ClientProfileService(CLIENTS, writer, events)


def main() -> None:
    print("=== Slice 15: Client Profiles ===\n")
    svc = build_service()
    org_scope = Scope(level=ScopeLevel.org)

    # --- Client list ---
    print("Client list (org scope):")
    clients = svc.list_clients(org_scope)
    check("returns 3 clients", len(clients) == 3)
    ids = {c["id"] for c in clients}
    check("all known IDs present", ids == KNOWN_CLIENT_IDS)
    northpath = next(c for c in clients if c["id"] == "client-northpath-001")
    check("Northpath has deal_stage=Proposal", northpath["deal_stage"] == "Proposal")
    vertex = next(c for c in clients if c["id"] == "client-vertex-002")
    check("Vertex has deal_stage=None", vertex["deal_stage"] is None)

    # --- Entity-scoped list ---
    print("\nClient list (entity scope = northpath):")
    entity_scope = Scope(level=ScopeLevel.entity, entity_ref="client-northpath-001")
    scoped = svc.list_clients(entity_scope)
    check("returns exactly 1 client", len(scoped) == 1)
    check("that client is northpath", scoped[0]["id"] == "client-northpath-001")

    # --- Client detail ---
    print("\nClient detail (northpath):")
    profile = svc.get_profile("client-northpath-001", org_scope)
    assert profile is not None
    check("name is Northpath", profile["name"] == "Northpath")
    check(
        "episodic_history non-empty",
        len(profile["brain_understanding"]["episodic_history"]) > 0,
    )
    check("live deal stage is Proposal", profile["live_status"]["deal"]["stage"] == "Proposal")
    check("live deal days_in_stage present", profile["live_status"]["deal"]["days_in_stage"] == 21)

    print("\nClient detail (meridian):")
    meridian = svc.get_profile("client-meridian-001", org_scope)
    assert meridian is not None
    check("has budget data", meridian["live_status"]["budget"] is not None)
    check("INV-007 in invoices", any(
        i["invoice_number"] == "INV-007"
        for i in meridian["live_status"]["invoices"]
    ))

    # --- Scope enforcement ---
    print("\nScope enforcement:")
    try:
        svc.get_profile(
            "client-northpath-001",
            Scope(level=ScopeLevel.entity, entity_ref="client-meridian-001"),
        )
        check("mismatched scope raises ScopeViolationError", False)
    except ScopeViolationError:
        check("mismatched scope raises ScopeViolationError", True)

    check("unknown client returns None", svc.get_profile("client-x", org_scope) is None)

    print("\n=== All checks passed ===")


if __name__ == "__main__":
    main()
