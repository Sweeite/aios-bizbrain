"""
Slice 10 prove script — Consolidation + reconciliation.
Run from backend/: .venv/bin/python scripts/prove_slice10.py
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from engine.spine.types import Confidence, MemoryRecord, MemoryStore, Scope, ScopeLevel
from engine.consolidation.consolidator import Consolidator
from engine.reconciliation.reconciler import Reconciler

NOW = datetime(2025, 3, 2, 0, 0, tzinfo=timezone.utc)
ENTITY = "client-vertex-002"
PATTERN = "invoice.paid_late"

# ── Consolidation ────────────────────────────────────────────────────────────
print("=== Consolidation ===")

scope = Scope(level=ScopeLevel.entity, entity_ref=ENTITY)
records = [
    MemoryRecord(
        store=MemoryStore.episodic,
        payload={"event_type": PATTERN, "days_late": 25 + i},
        provenance=f"quickbooks:qb-inv-{i:03d}",
        temporal_validity={"as_of": "2025-02-01", "lifespan_days": 365},
        scope=scope,
        confidence=Confidence.observed,
    )
    for i in range(10)
]

result = Consolidator().consolidate(ENTITY, PATTERN, records, NOW)
fact = result.promoted[0]

print(f"  Input:      10 episodic '{PATTERN}' records")
print(f"  Promoted:   {len(result.promoted)} entity fact")
print(f"  Summary:    \"{fact.payload['summary']}\"")
print(f"  Confidence: {fact.confidence}")
print(f"  Provenance: {fact.provenance}")
print(f"  Superseded: {len(result.superseded)} originals marked at {result.superseded[0].superseded_at}")

since = datetime(2025, 1, 1, tzinfo=timezone.utc)
digest = Consolidator().summarize(ENTITY, since, records, NOW)
print(f"\n  Digest:     {digest.payload['record_count']} records since {digest.payload['since'][:10]}")

# ── Reconciliation ───────────────────────────────────────────────────────────
print("\n=== Reconciliation ===")

reconciler = Reconciler(gap_threshold=2)
known = {"qb-inv-007-issued-2025-03-01", "qb-inv-006-paid-2025-03-01"}
available = list(known) + ["qb-inv-008-issued-2025-03-01", "qb-inv-009-issued-2025-03-01"]

r = reconciler.reconcile("quickbooks", known, available)
print(f"  System:       quickbooks")
print(f"  Checked:      {r.checked} events")
print(f"  Misses:       {r.misses}")
print(f"  Gap triggered:{r.gap_triggered}  (threshold=2, misses={len(r.misses)})")
print(f"  New cursor:   {r.cursor}")
print(f"  Stored cursor:{reconciler.get_cursor('quickbooks')}")
