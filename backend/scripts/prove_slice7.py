"""
Slice 7 proving script — Observability: trace tree, eval labels, audit log.

Runs in-process (no server required). Wires real stores into the FastAPI app
via dependency override, then exercises every acceptance criterion from issue #8.

Usage:
    cd backend
    .venv/bin/python scripts/prove_slice7.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from engine.agent.registry import AgentRegistry
from engine.agent.live import LiveQuery
from engine.agent.orchestrator import Orchestrator
from engine.agent.span_emitter import SpanEmitter
from engine.ingestion.memory_writer import MemoryWriter
from engine.observability.audit_store import InMemoryAuditStore
from engine.observability.run_store import InMemoryRunStore
from engine.observability.span_store import InMemorySpanStore
from engine.spine.types import (
    AgentSpec, AutonomyTier, Scope, ScopeLevel, SpanOp, ToolMode, ToolSpec,
)
from engine.tools.executor import ToolExecutor
from engine.tools.registry import ToolRegistry
from app.main import app
from app.approvals import get_executor
from app.deps import get_run_store, get_span_store

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


def _mock_anthropic(input_tokens: int = 120, output_tokens: int = 55):
    client = MagicMock()
    resp = MagicMock()
    resp.content[0].text = "Dear Northpath, following up on the pending proposal..."
    resp.usage.input_tokens = input_tokens
    resp.usage.output_tokens = output_tokens
    client.messages.create.return_value = resp
    return client


def _account_spec() -> AgentSpec:
    return AgentSpec(
        name="account-agent",
        role="Manages client relationships",
        scope=Scope(level=ScopeLevel.entity, entity_ref="__client__"),
        toolset=["gmail.draft_email"],
        model_tier={"default": "strong"},
        wake_triggers=["deal.stage_changed"],
        playbooks=["nudge-stalled-deal"],
        spawn_policy={},
    )


def _email_spec() -> ToolSpec:
    return ToolSpec(
        name="gmail.draft_email",
        inputs={"to": "str", "subject": "str", "body": "str"},
        system="gmail",
        mode=ToolMode.write,
        tier=AutonomyTier.T3,
        scope_required=ScopeLevel.entity,
        reversible=False,
        side_effects=["creates_email_draft"],
    )


# ---------------------------------------------------------------------------
# Step 1: Full proving-path run produces a complete trace tree
# ---------------------------------------------------------------------------

print("\n── Step 1: Full proving-path trace tree ──────────────────────────────")

span_store = InMemorySpanStore()
run_store = InMemoryRunStore()
audit_store = InMemoryAuditStore()
emitter = SpanEmitter(store=span_store)

tool_registry = ToolRegistry()
tool_registry.register(_email_spec(), lambda inputs, dry_run=False: inputs.get("body", ""))
executor = ToolExecutor(
    tool_registry,
    span_emitter=emitter,
    audit_store=audit_store,
)

registry = AgentRegistry()
registry.register(_account_spec())

orch = Orchestrator(
    registry=registry,
    memory_writer=MemoryWriter(),
    live=LiveQuery(),
    anthropic_client=_mock_anthropic(),
    span_emitter=emitter,
    run_store=run_store,
    tool_executor=executor,
    idempotency_key="prove-s7-001",
)

result = orch.handle("deal.stage_changed", "client-northpath-001")
run_id = result.span.run_id

spans = emitter.spans()
run = run_store.get(run_id)

check("Run record saved with run_id", run is not None, run_id)
check("Run status is done", run.status == "done", run.status)

actors = {s.actor for s in spans}
check("Memory-recall span emitted", "memory-writer" in actors, str(actors))
check("Agent-reasoning span emitted", "account-agent" in actors, str(actors))
check("Orchestrator span emitted", "orchestrator" in actors, str(actors))

check("All spans share one run_id", len({s.run_id for s in spans}) == 1)

print(f"       {len(spans)} spans in run {run_id[:8]}…")
for s in sorted(spans, key=lambda x: x.started_at):
    print(f"       actor={s.actor:<18} op={s.op.value:<7} tokens={s.token_in}in/{s.token_out}out")

# ---------------------------------------------------------------------------
# Step 2: Cost attribution — LLM tokens attributable via spans
# ---------------------------------------------------------------------------

print("\n── Step 2: Cost attribution ──────────────────────────────────────────")

total_in = sum(s.token_in for s in spans)
total_out = sum(s.token_out for s in spans)
check("token_in sum >= LLM input tokens (120)", total_in >= 120, f"sum={total_in}")
check("token_out sum >= LLM output tokens (55)", total_out >= 55, f"sum={total_out}")

# ---------------------------------------------------------------------------
# Step 3: Trace tree endpoint returns full span tree
# ---------------------------------------------------------------------------

print("\n── Step 3: GET /runs/{run_id}/trace endpoint ─────────────────────────")

app.dependency_overrides[get_span_store] = lambda: span_store
app.dependency_overrides[get_run_store] = lambda: run_store
http = TestClient(app)

resp = http.get(f"/runs/{run_id}/trace")
check("GET /runs/{run_id}/trace → 200", resp.status_code == 200, str(resp.status_code))
data = resp.json()
check("run_id in response", data["run_id"] == run_id)
check(f"trace has {len(spans)} spans", len(data["spans"]) == len(spans), str(len(data["spans"])))

resp404 = http.get("/runs/no-such-run/trace")
check("GET /runs/unknown → 404", resp404.status_code == 404)

# ---------------------------------------------------------------------------
# Step 4: Eval labels on approve / edit-then-approve / reject
# ---------------------------------------------------------------------------

print("\n── Step 4: Eval labels ───────────────────────────────────────────────")

# Approve → positive
emitter2 = SpanEmitter()
audit2 = InMemoryAuditStore()
reg2 = ToolRegistry()
reg2.register(_email_spec(), lambda inputs, dry_run=False: inputs.get("body", ""))
ex2 = ToolExecutor(reg2, span_emitter=emitter2, audit_store=audit2)
ex2.execute(
    "gmail.draft_email",
    inputs={"to": "x@y.com", "subject": "s", "body": "original"},
    scope=Scope(level=ScopeLevel.entity, entity_ref="client-1"),
    requesting_agent="account-agent",
    principal="client-1",
    rationale="test",
    idempotency_key="eval-approve",
    run_id="run-eval",
)
ex2.approve("eval-approve", approver="partner@firm.com")

tool_spans = [s for s in emitter2.spans() if s.op == SpanOp.tool]
check("Approve → eval_label=positive", tool_spans[0].eval_label == "positive",
      tool_spans[0].eval_label)

# Edit-then-approve → soft_negative
emitter3 = SpanEmitter()
reg3 = ToolRegistry()
reg3.register(_email_spec(), lambda inputs, dry_run=False: inputs.get("body", ""))
ex3 = ToolExecutor(reg3, span_emitter=emitter3)
ex3.execute(
    "gmail.draft_email",
    inputs={"to": "x@y.com", "subject": "s", "body": "original draft"},
    scope=Scope(level=ScopeLevel.entity, entity_ref="client-2"),
    requesting_agent="account-agent",
    principal="client-2",
    rationale="test",
    idempotency_key="eval-edit",
    run_id="run-eval",
)
ex3.approve("eval-edit", override_body="edited draft")

tool_spans3 = [s for s in emitter3.spans() if s.op == SpanOp.tool]
check("Edit-then-approve → eval_label=soft_negative", tool_spans3[0].eval_label == "soft_negative",
      tool_spans3[0].eval_label)
check("Edit note contains diff", tool_spans3[0].eval_note is not None)

# Reject → negative
emitter4 = SpanEmitter()
reg4 = ToolRegistry()
reg4.register(_email_spec(), lambda inputs, dry_run=False: inputs.get("body", ""))
ex4 = ToolExecutor(reg4, span_emitter=emitter4)
ex4.execute(
    "gmail.draft_email",
    inputs={"to": "x@y.com", "subject": "s", "body": "draft"},
    scope=Scope(level=ScopeLevel.entity, entity_ref="client-3"),
    requesting_agent="account-agent",
    principal="client-3",
    rationale="test",
    idempotency_key="eval-reject",
    run_id="run-eval",
)
ex4.reject("eval-reject", reason="not appropriate")

tool_spans4 = [s for s in emitter4.spans() if s.op == SpanOp.tool]
check("Reject → eval_label=negative", tool_spans4[0].eval_label == "negative",
      tool_spans4[0].eval_label)
check("Reject note is the reason", tool_spans4[0].eval_note == "not appropriate")

# ---------------------------------------------------------------------------
# Step 5: Audit log records approve/reject with before/after state
# ---------------------------------------------------------------------------

print("\n── Step 5: Audit log ─────────────────────────────────────────────────")

record = audit2.get("eval-approve")
check("Audit record written on approve", record is not None)
check("outcome = approved", record.outcome == "approved", record.outcome)
check("approver recorded", record.approver == "partner@firm.com", record.approver)
check("idempotency_key matches", record.idempotency_key == "eval-approve")
check("before_state is original preview", record.before_state == "original",
      repr(record.before_state))
check("after_state is approved body", record.after_state == "original",
      repr(record.after_state))

# ---------------------------------------------------------------------------
# Step 6: Audit records are immutable — UPDATE/DELETE raise ImmutableRecordError
# ---------------------------------------------------------------------------

print("\n── Step 6: Audit immutability ────────────────────────────────────────")

from engine.observability.audit_store import ImmutableRecordError

update_raised = False
try:
    audit2.update("eval-approve", {})
except ImmutableRecordError:
    update_raised = True

delete_raised = False
try:
    audit2.delete("eval-approve")
except ImmutableRecordError:
    delete_raised = True

check("UPDATE raises ImmutableRecordError", update_raised)
check("DELETE raises ImmutableRecordError", delete_raised)

# ---------------------------------------------------------------------------

print("\n\033[32m✓ All Slice 7 acceptance criteria verified.\033[0m\n")
