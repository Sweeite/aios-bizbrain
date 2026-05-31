# TESTING.md — Slice 1: Project Scaffold + Slice 2: Mock Ingestion + Slice 3: Celery + Redis

Manual verification steps for what cannot be covered by automated tests.

---

## 1. Backend — automated tests

```bash
cd backend
.venv/bin/python -m pytest -v
```

Expected: all tests pass (spine type validation + FastAPI health check).

---

## 2. FastAPI server boots

```bash
cd backend
cp ../.env.example .env        # fill in SUPABASE_URL and SUPABASE_ANON_KEY
.venv/bin/uvicorn app.main:app --reload
```

Open http://localhost:8000/health — expect:
```json
{"status": "ok", "supabase_url": true}
```

Open http://localhost:8000/docs — expect the FastAPI Swagger UI to load.

---

## 3. Supabase schema applies

```bash
# Install Supabase CLI if not present:
brew install supabase/tap/supabase

# Link to your project:
cd backend
supabase link --project-ref <your-project-ref>

# Push the migration:
supabase db push
```

Expected: all 12 tables created without errors in the Supabase dashboard:
- `entity_memory`, `semantic_memory`, `episodic_memory`, `procedural_memory`
- `intake_queue`, `tool_registry`, `agent_registry`, `autonomy_config`
- `audit_log`, `runs`, `spans`, `approval_queue`

---

## 4. FastAPI connects to Supabase

With `.env` filled in, restart the server and confirm `supabase_url: true` in the health response.

If false: verify `SUPABASE_URL` is set correctly in `.env`.

---

## 5. Next.js cockpit loads

```bash
cd cockpit
cp .env.local.example .env.local   # fill in NEXT_PUBLIC_SUPABASE_URL etc.
npm run dev
```

Open http://localhost:3000 — expect:
- "AIOS BizBrain" heading renders
- "Cockpit — Slice 1 scaffold" subtitle renders
- shadcn/ui styles applied (dark mode toggle works if OS is dark)

Open http://localhost:3000/cockpit — expect the slice roadmap list renders.

---

## 6. API health proxy (cockpit → backend)

With both backend (port 8000) and cockpit (port 3000) running:

Open http://localhost:3000/api/health — expect:
```json
{"cockpit": "ok", "api": {"status": "ok", "supabase_url": true}}
```

If `api: "unreachable"`: confirm backend is running on port 8000.

---

## 7. Three-layer separation check

Run from repo root:
```bash
grep -r "northpath\|Northpath" backend/engine/ && echo "FAIL: engine contains client refs" || echo "PASS: engine is clean"
```

Expected: `PASS: engine is clean`

---

## 8. prompt-kit

prompt-kit is a shadcn registry library for AI chat components. The correct registry base URL is `https://www.prompt-kit.com/c/` (not `/r/`).

The `message` component was installed in Slice 6. Install the `prompt-input` component when building the chat interface in Slice 8:

```bash
cd cockpit
npx shadcn@latest add https://www.prompt-kit.com/c/prompt-input.json
```

---

## 9. Pack imports resolve

```bash
cd backend
PYTHONPATH=.. .venv/bin/python -c "
from packs.consulting.tool_catalog import CONSULTING_TOOLS
from packs.consulting.agent_specs import CONSULTING_AGENTS
from packs.consulting.event_taxonomy import ConsultingEventType
from config.northpath import CLIENT_NAME, AUTONOMY_OVERRIDES
print('tools:', len(CONSULTING_TOOLS))
print('agents:', len(CONSULTING_AGENTS))
print('client:', CLIENT_NAME)
print('PASS')
"
```

Expected:
```
tools: 11
agents: 4
client: Northpath
PASS
```

---

## Slice 2: Mock Ingestion

### 10. Automated tests (ingestion)

```bash
cd backend
.venv/bin/python -m pytest tests/test_ingestion.py -v
```

Expected: 14 ingestion tests pass alongside the existing 31 spine tests (45 total).

---

### 11. Episodic row visible in Supabase

Run the ingestion script to push the fixture event to your linked Supabase project:

```bash
cd backend
PYTHONPATH=.. .venv/bin/python - <<'EOF'
import sys, os
sys.path.insert(0, '..')
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
from engine.ingestion.entity_resolver import EntityResolver
from packs.consulting.connectors.hubspot_mock import HubSpotMockConnector

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_ANON_KEY"]
db = create_client(url, key)

events = HubSpotMockConnector().pull()
resolver = EntityResolver(known_entities={"client-northpath-001": "client"})

for event in events:
    resolved = resolver.resolve(event)
    ev = resolved.event
    row = {
        "source_event_id": ev.id,
        "source_system":   ev.source_system,
        "event_type":      ev.event_type,
        "payload":         ev.body | {"event_type": ev.event_type},
        "provenance":      f"{ev.source_system}:{ev.id}",
        "as_of":           ev.timestamp.isoformat(),
        "lifespan_days":   365,
        "scope_level":     resolved.scope.level.value,
        "scope_entity_ref": resolved.scope.entity_ref,
        "confidence":      resolved.confidence.value,
    }
    db.table("episodic_memory").upsert(row, on_conflict="source_event_id,source_system").execute()
    print("Wrote:", ev.id)

print("PASS — check Supabase Table Editor → episodic_memory")
EOF
```

Expected: script prints `Wrote: hs-deal-99-stage-changed-2025-03-01` then `PASS`.  
In the Supabase dashboard → Table Editor → `episodic_memory`, you should see a row with:
- `source_event_id = hs-deal-99-stage-changed-2025-03-01`
- `event_type = deal.stage_changed`
- `scope_entity_ref = client-northpath-001`
- `confidence = observed`

Running the script a second time must produce the same row (idempotent — `UNIQUE(source_event_id, source_system)` prevents duplicates).

---

### 12. Three-layer separation check (engine has no pack/client refs)

```bash
grep -r "northpath\|Northpath\|hubspot_mock\|consulting" backend/engine/ \
  && echo "FAIL: engine contains pack/client refs" \
  || echo "PASS: engine is clean"
```

Expected: `PASS: engine is clean`

---

## Slice 3: Celery + Redis

### 13. Automated tests (worker + reflection hook)

```bash
cd backend
.venv/bin/python -m pytest tests/test_worker.py -v
```

Expected: 8 new tests pass (53 total).

---

### 14. Celery worker boots

Requires `REDIS_URL` in `.env` pointing to a running Redis instance (Railway service or local Docker).

```bash
cd backend
.venv/bin/celery -A engine.worker.celery_app.celery_app worker --loglevel=info
```

Expected: worker starts and lists `engine.worker.tasks.reflection.reflect_on_memory_write` in registered tasks.

---

### 15. Reflection hook fires after ingestion

With the Celery worker running in one terminal, run the ingestion script from step 11 in another:

```bash
cd backend
PYTHONPATH=.. .venv/bin/python - <<'EOF'
import os, sys
sys.path.insert(0, '..')
from dotenv import load_dotenv
load_dotenv()

from engine.ingestion.entity_resolver import EntityResolver
from engine.ingestion.memory_writer import MemoryWriter
from engine.worker.tasks.reflection import reflect_on_memory_write
from packs.consulting.connectors.hubspot_mock import HubSpotMockConnector

events = HubSpotMockConnector().pull()
resolver = EntityResolver(known_entities={"client-northpath-001": "client"})
writer = MemoryWriter(on_write=reflect_on_memory_write.delay)

for event in events:
    resolved = resolver.resolve(event)
    writer.write(resolved)
    print("Wrote and queued reflection for:", event.id)

print("PASS — check Celery worker terminal for reflection hook log line")
EOF
```

Expected:
- Script prints `Wrote and queued reflection for: hs-deal-99-stage-changed-2025-03-01`  
- Celery worker terminal shows a line like: `reflection hook fired: event=hs-deal-99-stage-changed-2025-03-01 system=hubspot entity=client-northpath-001`

---

### 16. No FastAPI BackgroundTasks used anywhere

```bash
grep -r "BackgroundTasks\|background_tasks" backend/app/ backend/engine/ \
  && echo "FAIL: BackgroundTasks found" \
  || echo "PASS: no BackgroundTasks"
```

Expected: `PASS: no BackgroundTasks`

---

## Slice 4: Account Agent + Orchestrator

### 17. Automated tests (agent)

```bash
cd backend
.venv/bin/python -m pytest tests/test_agent.py -v
```

Expected: 27 new tests pass (80 total).

---

### 18. Trigger the fixture event and confirm a draft nudge is produced

Requires `ANTHROPIC_API_KEY` set in `backend/.env`.

```bash
cd backend
.venv/bin/python - <<'EOF'
import os, sys
sys.path.insert(0, '..')
from dotenv import load_dotenv
load_dotenv()

import anthropic
from engine.agent.registry import AgentRegistry
from engine.agent.live import LiveQuery
from engine.agent.span_emitter import SpanEmitter
from engine.agent.orchestrator import Orchestrator
from engine.ingestion.entity_resolver import EntityResolver
from engine.ingestion.memory_writer import MemoryWriter
from packs.consulting.agent_specs.roster import CONSULTING_AGENTS
from packs.consulting.connectors.hubspot_mock import HubSpotMockConnector

# Build memory from fixture event
events = HubSpotMockConnector().pull()
resolver = EntityResolver(known_entities={"client-northpath-001": "client"})
writer = MemoryWriter()
for event in events:
    writer.write(resolver.resolve(event))

# Wire registry from pack
registry = AgentRegistry()
for spec in CONSULTING_AGENTS:
    registry.register(spec)

# Run orchestrator
emitter = SpanEmitter()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
orch = Orchestrator(
    registry=registry,
    memory_writer=writer,
    live=LiveQuery(),
    anthropic_client=client,
    span_emitter=emitter,
)
result = orch.handle("deal.stage_changed", "client-northpath-001")

print("=== Draft nudge ===")
print(result.draft)
print()
print("=== Span ===")
s = emitter.spans()[0]
print(f"actor={s.actor}  model={s.model_tier}  token_in={s.token_in}  token_out={s.token_out}")
print("PASS")
EOF
```

Expected:
- A draft nudge email printed to stdout
- Span line showing `actor=account-agent  model=claude-sonnet-4-6  token_in=<n>  token_out=<n>`

---

### 19. Span row visible in Supabase

After running step 18, push the span to Supabase:

```bash
cd backend
.venv/bin/python - <<'EOF'
import os, sys
sys.path.insert(0, '..')
from dotenv import load_dotenv
load_dotenv(".env")

import anthropic
from datetime import datetime, timezone
from supabase import create_client
from engine.agent.registry import AgentRegistry
from engine.agent.live import LiveQuery
from engine.agent.span_emitter import SpanEmitter
from engine.agent.orchestrator import Orchestrator
from engine.ingestion.entity_resolver import EntityResolver
from engine.ingestion.memory_writer import MemoryWriter
from packs.consulting.agent_specs.roster import CONSULTING_AGENTS
from packs.consulting.connectors.hubspot_mock import HubSpotMockConnector

events = HubSpotMockConnector().pull()
writer = MemoryWriter()
for e in events:
    writer.write(EntityResolver(known_entities={"client-northpath-001": "client"}).resolve(e))

registry = AgentRegistry()
for spec in CONSULTING_AGENTS:
    registry.register(spec)

emitter = SpanEmitter()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
orch = Orchestrator(
    registry=registry, memory_writer=writer,
    live=LiveQuery(), anthropic_client=client, span_emitter=emitter,
)
orch.handle("deal.stage_changed", "client-northpath-001")

db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])
span = emitter.spans()[0]

# Insert parent run first (spans.run_id is a FK to runs)
db.table("runs").upsert({
    "run_id":           span.run_id,
    "initiated_by":     "orchestrator",
    "scope_level":      span.scope.level.value,
    "scope_entity_ref": span.scope.entity_ref,
    "started_at":       span.started_at.isoformat(),
    "status":           "completed",
}, on_conflict="run_id").execute()

db.table("spans").upsert({
    "span_id":          span.span_id,
    "run_id":           span.run_id,
    "actor":            span.actor,
    "op":               span.op.value,
    "model_tier":       span.model_tier,
    "token_in":         span.token_in,
    "token_out":        span.token_out,
    "scope_level":      span.scope.level.value,
    "scope_entity_ref": span.scope.entity_ref,
    "status":           span.status,
    "outcome":          span.outcome,
    "started_at":       span.started_at.isoformat(),
    "ended_at":         span.ended_at.isoformat() if span.ended_at else None,
}, on_conflict="span_id").execute()

print(f"Wrote run:  {span.run_id}")
print(f"Wrote span: {span.span_id}  actor={span.actor}  tokens={span.token_in}+{span.token_out}")
print("PASS — check Supabase Table Editor → runs + spans")
EOF
```

Expected: span row in Supabase `spans` table with:
- `actor = account-agent`
- `model_tier = claude-sonnet-4-6`
- `op = reason`
- `outcome = draft_nudge`
- `token_in` and `token_out` > 0

---

### 20. Three-layer separation check (engine/agent has no pack/client refs)

```bash
grep -r "northpath\|Northpath\|hubspot_mock\|consulting" backend/engine/ \
  && echo "FAIL: engine contains pack/client refs" \
  || echo "PASS: engine is clean"
```

Expected: `PASS: engine is clean`

---

## Slice 5: Commitment gate + T3 tool — draft email parks as ParkedApprovalRequest

### 21. Automated tests (tools + commitment gate)

```bash
cd backend
.venv/bin/python -m pytest tests/test_tools.py -v
```

Expected: 33 tests pass.

---

### 22. Trigger the proving path — confirm parked request row in Supabase

Requires `ANTHROPIC_API_KEY`, `SUPABASE_URL`, and `SUPABASE_ANON_KEY` in `backend/.env`.

```bash
cd backend
.venv/bin/python - <<'EOF'
import os, sys
sys.path.insert(0, '..')
from dotenv import load_dotenv
load_dotenv()

import anthropic
from supabase import create_client
from engine.agent.registry import AgentRegistry
from engine.agent.live import LiveQuery
from engine.agent.span_emitter import SpanEmitter
from engine.agent.orchestrator import Orchestrator
from engine.ingestion.entity_resolver import EntityResolver
from engine.ingestion.memory_writer import MemoryWriter
from engine.spine.types import ParkedApprovalRequest
from engine.tools.registry import ToolRegistry
from engine.tools.executor import ToolExecutor
from engine.tools.implementations.draft_email import DraftEmailTool, SPEC as EMAIL_SPEC
from packs.consulting.agent_specs.roster import CONSULTING_AGENTS
from packs.consulting.connectors.hubspot_mock import HubSpotMockConnector

db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])

def park_to_supabase(req: ParkedApprovalRequest) -> None:
    db.table("approval_queue").upsert({
        "idempotency_key":   req.idempotency_key,
        "action":            req.action,
        "preview":           req.preview,
        "requesting_agent":  req.requesting_agent,
        "principal":         req.principal,
        "scope_level":       req.scope.level.value,
        "scope_entity_ref":  req.scope.entity_ref,
        "rationale":         req.rationale,
        "status":            "pending",
    }, on_conflict="idempotency_key").execute()
    print(f"Parked: action={req.action!r}  key={req.idempotency_key!r}")

# Build tool executor with Supabase on_park callback
tool_registry = ToolRegistry()
tool_registry.register(EMAIL_SPEC, DraftEmailTool().execute)
executor = ToolExecutor(tool_registry, on_park=park_to_supabase)

# Build memory from fixture event
events = HubSpotMockConnector().pull()
resolver = EntityResolver(known_entities={"client-northpath-001": "client"})
writer = MemoryWriter()
for event in events:
    writer.write(resolver.resolve(event))

# Wire agent registry
agent_registry = AgentRegistry()
for spec in CONSULTING_AGENTS:
    agent_registry.register(spec)

# Run orchestrator (passes executor so agent can call tools)
emitter = SpanEmitter()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
orch = Orchestrator(
    registry=agent_registry,
    memory_writer=writer,
    live=LiveQuery(),
    anthropic_client=client,
    span_emitter=emitter,
    tool_executor=executor,
    idempotency_key="slice5-proving-path-001",
)
result = orch.handle("deal.stage_changed", "client-northpath-001")

print()
print("=== Draft nudge ===")
print(result.draft)
print()
if result.parked:
    print(f"=== Parked as T3 ===  key={result.parked.idempotency_key!r}")
else:
    print("(No commitment detected — sent as autonomous T1)")
print("PASS — check Supabase Table Editor → approval_queue")
EOF
```

Expected:
- Script prints `Parked: action='gmail.draft_email'  key='slice5-proving-path-001'`
- Draft nudge printed to stdout
- `Parked as T3` line printed

In the Supabase dashboard → Table Editor → `approval_queue`, confirm a row with:
- `action = gmail.draft_email`
- `status = pending`
- `requesting_agent = account-agent`
- `preview` = the exact draft email body
- `idempotency_key = slice5-proving-path-001`

Running the script a second time must produce the same row (idempotent — `UNIQUE(idempotency_key)` prevents duplicates, `on_park` callback does not fire again).

---

### 23. Idempotency check — same key parks once

Re-run the script from step 22 without changing `idempotency_key`. Confirm:
- `approval_queue` still has exactly one row for `idempotency_key = slice5-proving-path-001`
- Row is not duplicated or overwritten with a different preview

---

### 24. Three-layer separation check

```bash
grep -r "northpath\|Northpath\|hubspot_mock\|consulting" backend/engine/ \
  && echo "FAIL: engine contains pack/client refs" \
  || echo "PASS: engine is clean"
```

Expected: `PASS: engine is clean`

---

## Slice 6: Approval Queue — end-to-end proving path

### 25. Automated tests (approvals + tools augmentation)

```bash
cd backend
.venv/bin/python -m pytest tests/test_tools.py tests/test_approvals.py -v
```

Expected: 47 tool tests + 16 approval tests = 63 tests pass.

---

### 26. Backend endpoints smoke-check

With the FastAPI server running (`cd backend && .venv/bin/uvicorn app.main:app --reload`):

```bash
# List empty queue
curl -s http://localhost:8000/approvals | python3 -m json.tool
# → []

# Approve unknown key → 404
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/approvals/no-such-key/approve
# → 404

# Reject unknown key → 404
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/approvals/no-such-key/reject \
  -H "Content-Type: application/json" -d '{"reason":"test"}'
# → 404
```

---

### 27. Full end-to-end proving path

Requires `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` in `backend/.env`.
FastAPI server must be running on port 8000.

Run the Slice 5 proving script (step 22) — this parks a request in Supabase AND in the
in-memory executor. Because the executor lives in the FastAPI process, the parked request
is queryable immediately via the API.

Then verify via the cockpit:

```bash
cd cockpit && npm run dev
```

Open http://localhost:3000/cockpit/approvals — expect:
- The Approval Queue page loads with the parked request visible
- Card shows: draft email preview, agent rationale, entity ref, scope level
- Three buttons: Approve, Edit & Approve, Reject

**Approve:**
1. Click **Approve** on the card
2. Card disappears from the queue
3. Confirm via `curl http://localhost:8000/approvals` — queue is empty
4. Approve same key again (idempotency check):
   ```bash
   curl -s -X POST http://localhost:8000/approvals/<key>/approve \
     -H "Content-Type: application/json" -d '{}'
   ```
   → returns `{"status":"approved","result":"..."}` (idempotent — not 404 or 5xx)

**Edit & Approve:**
1. Re-park a fresh request using the proving script with a new idempotency key
2. Click **Edit & Approve** — textarea expands showing the draft
3. Modify the text
4. Click **Approve with edits**
5. Card disappears; `result` field in the approve response contains the edited text (not original)

**Reject:**
1. Re-park a fresh request
2. Click **Reject** — reason input appears
3. Type a reason and click **Confirm rejection**
4. Card disappears from queue
5. Reject same key again (idempotency check):
   ```bash
   curl -s -X POST http://localhost:8000/approvals/<key>/reject \
     -H "Content-Type: application/json" -d '{"reason":"second attempt"}'
   ```
   → returns `{"status":"rejected"}` (idempotent)


---

## Slice 16: Cockpit — Integrations / Health

### QA-2: Integrations page

With both backend and cockpit running:

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload
cd cockpit && npm run dev
```

**Healthy state:**

Open http://localhost:3000/cockpit/integrations — expect:
- All 8 connectors listed: HubSpot, Gmail, Google Calendar, Asana, Slack, QuickBooks, Harvest, Zoom
- Each shows a green "Healthy" badge
- Last sync shows "Never" (no syncs have run yet)
- No reconnect buttons visible
- No alert banner at the top

**Broken connector state:**

Simulate a broken connector via the API:

```bash
# Trigger a failed sync for gmail
curl -s http://localhost:8000/integrations/health | python3 -m json.tool
# → all 8 connectors, status=healthy

# There is no direct "break" endpoint — this is simulated in tests.
# To manually test: restart the server and use the test override pattern
# (see tests/test_integrations.py TestBrokenConnectorSurfaces).
```

In the automated test, `svc.record_sync("gmail", success=False, error_message="auth_expired")` sets the
broken state. Verify the UI:
- Gmail row shows a red "Broken" badge
- Error message `auth_expired` appears in a red alert box below the row
- A "Reconnect" button appears on the Gmail row
- A banner at the top reads "1 connector needs attention"
- All other connectors remain green "Healthy"

**Reconnect action:**

```bash
curl -s -X POST http://localhost:8000/integrations/gmail/reconnect | python3 -m json.tool
# → {"source_system": "gmail", "status": "healthy", "last_sync_at": null, "error_message": null}
```

In the UI, clicking "Reconnect" on a broken connector:
- Button shows "Reconnecting…" while the request is in flight
- On success the page refreshes and Gmail shows as "Healthy" again
- No alert banner or error block visible

**Unknown connector 404:**

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/integrations/not_a_system/reconnect
# → 404
```
