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

## 8. prompt-kit (deferred — Slice 8)

prompt-kit is a shadcn registry library for AI chat components. Install it when building the chat interface in Slice 8:

```bash
cd cockpit
npx shadcn@latest add https://prompt-kit.com/r/prompt-input.json
npx shadcn@latest add https://prompt-kit.com/r/message.json
```

Not required for Slice 1 to pass.

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
