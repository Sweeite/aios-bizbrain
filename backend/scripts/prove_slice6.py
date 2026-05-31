"""
Slice 6 proving script — Approval Queue end-to-end.

Runs in-process (no server required). Wires a real ToolExecutor into the
FastAPI app via dependency override, then exercises every acceptance criterion
from issue #7 via HTTP.

Usage:
    cd backend
    .venv/bin/python scripts/prove_slice6.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient

from engine.spine.types import AutonomyTier, Scope, ScopeLevel, ToolMode, ToolSpec
from engine.tools.registry import ToolRegistry
from engine.tools.executor import ToolExecutor
from app.main import app
from app.approvals import get_executor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

def check(label: str, cond: bool, detail: str = "") -> None:
    mark = PASS if cond else FAIL
    suffix = f"  ({detail})" if detail else ""
    print(f"  {mark}  {label}{suffix}")
    if not cond:
        sys.exit(1)


def _make_executor() -> tuple[ToolExecutor, list]:
    """Fresh executor with a T3 draft-email tool. Returns (executor, call_log)."""
    call_log: list[dict] = []

    spec = ToolSpec(
        name="gmail.draft_email",
        inputs={"to": "str", "subject": "str", "body": "str"},
        system="gmail",
        mode=ToolMode.write,
        tier=AutonomyTier.T3,
        scope_required=ScopeLevel.entity,
        reversible=False,
        side_effects=["creates_email_draft"],
    )

    def fn(inputs: dict, dry_run: bool = False) -> str:
        call_log.append({"inputs": dict(inputs), "dry_run": dry_run})
        return inputs.get("body", "")

    registry = ToolRegistry()
    registry.register(spec, fn)
    return ToolExecutor(registry), call_log


def _park(executor: ToolExecutor, key: str, body: str = "Dear Northpath, following up on the proposal.") -> None:
    executor.execute(
        "gmail.draft_email",
        inputs={"to": "northpath@example.com", "subject": "Following up", "body": body},
        scope=Scope(level=ScopeLevel.entity, entity_ref="client-northpath-001"),
        requesting_agent="account-agent",
        principal="client-northpath-001",
        rationale="Commitment detected — confirming scope and fees.",
        idempotency_key=key,
    )


def _make_client(executor: ToolExecutor) -> TestClient:
    app.dependency_overrides[get_executor] = lambda: executor
    return TestClient(app)


# ---------------------------------------------------------------------------
# Step 1: Empty queue
# ---------------------------------------------------------------------------

print("\n── Step 1: Empty queue ───────────────────────────────────────────────")
executor, _ = _make_executor()
client = _make_client(executor)

resp = client.get("/approvals")
check("GET /approvals returns 200", resp.status_code == 200)
check("Queue is empty", resp.json() == [], str(resp.json()))

# ---------------------------------------------------------------------------
# Step 2: Parked request appears in queue
# ---------------------------------------------------------------------------

print("\n── Step 2: Parked request appears in queue ───────────────────────────")
_park(executor, "prove-key-001")

resp = client.get("/approvals")
data = resp.json()
check("Queue has 1 item", len(data) == 1, f"got {len(data)}")
item = data[0]
check("idempotency_key correct", item["idempotency_key"] == "prove-key-001")
check("action correct", item["action"] == "gmail.draft_email")
check("requesting_agent correct", item["requesting_agent"] == "account-agent")
check("rationale present", "Commitment detected" in item["rationale"])
check("preview is draft body", "Northpath" in item["preview"])
print(f"       preview: {item['preview'][:60]}…")

# ---------------------------------------------------------------------------
# Step 3: Approve — tool executes, request leaves queue
# ---------------------------------------------------------------------------

print("\n── Step 3: Approve ───────────────────────────────────────────────────")
executor2, call_log2 = _make_executor()
client2 = _make_client(executor2)
_park(executor2, "prove-key-002", body="Dear Client, confirming the Q3 audit scope.")
call_log2.clear()  # discard dry_run preview call

resp = client2.post("/approvals/prove-key-002/approve")
check("POST /approve returns 200", resp.status_code == 200)
check("status == approved", resp.json()["status"] == "approved")
check("result contains draft body", "Q3 audit" in resp.json()["result"])
check("fn called once with dry_run=False", call_log2 == [{"inputs": {"to": "northpath@example.com", "subject": "Following up", "body": "Dear Client, confirming the Q3 audit scope."}, "dry_run": False}])

resp = client2.get("/approvals")
check("Queue is empty after approve", resp.json() == [])

# ---------------------------------------------------------------------------
# Step 4: Idempotency — approving twice fires fn once
# ---------------------------------------------------------------------------

print("\n── Step 4: Idempotency — approve twice ───────────────────────────────")
executor3, call_log3 = _make_executor()
client3 = _make_client(executor3)
_park(executor3, "prove-key-003")
call_log3.clear()

r1 = client3.post("/approvals/prove-key-003/approve")
r2 = client3.post("/approvals/prove-key-003/approve")
check("First approve → 200", r1.status_code == 200)
check("Second approve → 200 (not 404/5xx)", r2.status_code == 200)
check("Both return same result", r1.json()["result"] == r2.json()["result"])
check("fn called exactly once", len(call_log3) == 1, f"called {len(call_log3)} times")

# ---------------------------------------------------------------------------
# Step 5: Edit-then-approve — modified body is what executes
# ---------------------------------------------------------------------------

print("\n── Step 5: Edit-then-approve ─────────────────────────────────────────")
executor4, call_log4 = _make_executor()
client4 = _make_client(executor4)
_park(executor4, "prove-key-004", body="Original draft — do not send as-is.")
call_log4.clear()

resp = client4.post(
    "/approvals/prove-key-004/approve",
    json={"body": "Dear Northpath, edited and approved: commencing June 1."},
)
check("Edit-then-approve → 200", resp.status_code == 200)
check("Result is the edited body (not original)", resp.json()["result"] == "Dear Northpath, edited and approved: commencing June 1.")
check("Original body NOT in result", "Original draft" not in resp.json()["result"])

resp = client4.get("/approvals")
check("Queue empty after edit-approve", resp.json() == [])

# ---------------------------------------------------------------------------
# Step 6: Reject-with-reason — removed from queue, idempotent
# ---------------------------------------------------------------------------

print("\n── Step 6: Reject-with-reason ────────────────────────────────────────")
executor5, _ = _make_executor()
client5 = _make_client(executor5)
_park(executor5, "prove-key-005")

resp = client5.post(
    "/approvals/prove-key-005/reject",
    json={"reason": "Scope not yet finalised — do not commit."},
)
check("POST /reject → 200", resp.status_code == 200)
check("status == rejected", resp.json()["status"] == "rejected")

resp = client5.get("/approvals")
check("Queue empty after reject", resp.json() == [])

# Second reject — idempotent
resp2 = client5.post(
    "/approvals/prove-key-005/reject",
    json={"reason": "second attempt"},
)
check("Reject same key twice → 200 (idempotent)", resp2.status_code == 200)

# ---------------------------------------------------------------------------
# Step 7: Unknown key → 404
# ---------------------------------------------------------------------------

print("\n── Step 7: Unknown key → 404 ─────────────────────────────────────────")
executor6, _ = _make_executor()
client6 = _make_client(executor6)

check("Approve unknown key → 404", client6.post("/approvals/no-such-key/approve").status_code == 404)
check("Reject unknown key → 404", client6.post("/approvals/no-such-key/reject", json={"reason": "test"}).status_code == 404)

# ---------------------------------------------------------------------------

print("\n\033[32m✓ All Slice 6 acceptance criteria verified.\033[0m\n")
