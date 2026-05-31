"""
Slice 14 proving script — Activity Feed.

Wires real stores into the FastAPI app, runs the Orchestrator to generate a
real run + spans, then exercises GET /activity and GET /runs/{run_id}/trace.

Usage:
    cd backend
    python scripts/prove_slice14.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from engine.agent.orchestrator import Orchestrator
from engine.agent.registry import AgentRegistry
from engine.agent.live import LiveQuery
from engine.agent.span_emitter import SpanEmitter
from engine.ingestion.memory_writer import MemoryWriter
from engine.observability.run_store import InMemoryRunStore
from engine.observability.span_store import InMemorySpanStore
from engine.spine.types import (
    AgentSpec, AutonomyTier, Scope, ScopeLevel, ToolMode, ToolSpec,
)
from engine.tools.executor import ToolExecutor
from engine.tools.registry import ToolRegistry
from app.main import app
from app.deps import get_run_store, get_span_store

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"


def check(label: str, cond: bool, detail: str = "") -> None:
    mark = PASS if cond else FAIL
    suffix = f"  ({detail})" if detail else ""
    print(f"  {mark}  {label}{suffix}")
    if not cond:
        sys.exit(1)


def _mock_anthropic():
    client = MagicMock()
    resp = MagicMock()
    resp.content[0].text = "Dear Northpath, following up on the stalled proposal..."
    resp.usage.input_tokens = 120
    resp.usage.output_tokens = 55
    client.messages.create.return_value = resp
    return client


# ---------------------------------------------------------------------------
# Build shared stores + orchestrator
# ---------------------------------------------------------------------------

run_store = InMemoryRunStore()
span_store = InMemorySpanStore()
emitter = SpanEmitter(store=span_store)

tool_registry = ToolRegistry()
tool_registry.register(
    ToolSpec(
        name="gmail.draft_email",
        inputs={"to": "str", "subject": "str", "body": "str"},
        system="gmail",
        mode=ToolMode.write,
        tier=AutonomyTier.T3,
        scope_required=ScopeLevel.entity,
        reversible=False,
        side_effects=["creates_email_draft"],
    ),
    lambda inputs, dry_run=False: inputs.get("body", ""),
)
executor = ToolExecutor(tool_registry, span_emitter=emitter)

agent_registry = AgentRegistry()
agent_registry.register(AgentSpec(
    name="account-agent",
    role="Manages client relationships",
    scope=Scope(level=ScopeLevel.entity, entity_ref="__client__"),
    toolset=["gmail.draft_email"],
    model_tier={"default": "strong"},
    wake_triggers=["deal.stage_changed"],
    playbooks=["nudge-stalled-deal"],
    spawn_policy={},
))

orch = Orchestrator(
    registry=agent_registry,
    memory_writer=MemoryWriter(),
    live=LiveQuery(),
    anthropic_client=_mock_anthropic(),
    span_emitter=emitter,
    run_store=run_store,
    tool_executor=executor,
    idempotency_key="prove-s14-001",
)

# Run a second orchestrator for a different client to test scope filter
run_store2_shared = run_store  # same store, different entity_ref
orch2 = Orchestrator(
    registry=agent_registry,
    memory_writer=MemoryWriter(),
    live=LiveQuery(),
    anthropic_client=_mock_anthropic(),
    span_emitter=emitter,
    run_store=run_store,
    tool_executor=executor,
    idempotency_key="prove-s14-002",
)

# ---------------------------------------------------------------------------
# Step 1: Run orchestrator and verify run/spans recorded
# ---------------------------------------------------------------------------

print("\n── Step 1: Orchestrator run produces run + spans ─────────────────────")

result1 = orch.handle("deal.stage_changed", "client-northpath-001")
run_id_1 = result1.span.run_id
result2 = orch2.handle("deal.stage_changed", "client-acme-002")
run_id_2 = result2.span.run_id

check("Run 1 saved", run_store.get(run_id_1) is not None, run_id_1[:12])
check("Run 2 saved", run_store.get(run_id_2) is not None, run_id_2[:12])
check("Spans recorded for run 1", len(span_store.get_by_run(run_id_1)) > 0)

# ---------------------------------------------------------------------------
# Step 2: GET /activity returns both runs reverse-chron
# ---------------------------------------------------------------------------

print("\n── Step 2: GET /activity ─────────────────────────────────────────────")

app.dependency_overrides[get_run_store] = lambda: run_store
app.dependency_overrides[get_span_store] = lambda: span_store
http = TestClient(app)

resp = http.get("/activity")
check("GET /activity → 200", resp.status_code == 200, str(resp.status_code))
data = resp.json()
check("Returns 2 runs", len(data) == 2, str(len(data)))
check("run_id present", "run_id" in data[0])
check("trigger present", "trigger" in data[0])
check("trigger_type present", "trigger_type" in data[0])
check("primary_agent present", "primary_agent" in data[0])
check("outcome present", "outcome" in data[0])
check("started_at present", "started_at" in data[0])
check("trigger_type = proactive", data[0]["trigger_type"] == "proactive",
      data[0]["trigger_type"])
check("outcome = completed", data[0]["outcome"] == "completed", data[0]["outcome"])
check("primary_agent = account-agent", data[0]["primary_agent"] == "account-agent",
      str(data[0]["primary_agent"]))

print(f"       run[0]: trigger={data[0]['trigger']}, agent={data[0]['primary_agent']}, outcome={data[0]['outcome']}")

# ---------------------------------------------------------------------------
# Step 3: GET /activity?scope= filters correctly
# ---------------------------------------------------------------------------

print("\n── Step 3: Scope filter ──────────────────────────────────────────────")

resp_scoped = http.get("/activity?scope=client-northpath-001")
check("Scope filter → 200", resp_scoped.status_code == 200)
scoped = resp_scoped.json()
check("Scope filter returns 1 run", len(scoped) == 1, str(len(scoped)))
check("Filtered run is for northpath",
      scoped[0]["run_id"] == run_id_1 or run_store.get(scoped[0]["run_id"]).scope.entity_ref == "client-northpath-001")

# ---------------------------------------------------------------------------
# Step 4: GET /runs/{run_id}/trace returns full span tree
# ---------------------------------------------------------------------------

print("\n── Step 4: GET /runs/{run_id}/trace ──────────────────────────────────")

resp_trace = http.get(f"/runs/{run_id_1}/trace")
check("GET /runs/{run_id}/trace → 200", resp_trace.status_code == 200,
      str(resp_trace.status_code))
trace = resp_trace.json()
check("run_id in response", trace["run_id"] == run_id_1)
check("spans present", len(trace["spans"]) > 0, str(len(trace["spans"])))

actors = [s["actor"] for s in trace["spans"]]
check("account-agent span in trace", "account-agent" in actors, str(actors))

print(f"       {len(trace['spans'])} spans:")
for s in trace["spans"]:
    print(f"       actor={s['actor']:<18} op={s['op']:<7} tokens={s['token_in']}in/{s['token_out']}out")

resp404 = http.get("/runs/no-such-run/trace")
check("Unknown run_id → 404", resp404.status_code == 404)

# ---------------------------------------------------------------------------

print("\n\033[32m✓ All Slice 14 acceptance criteria verified.\033[0m\n")
