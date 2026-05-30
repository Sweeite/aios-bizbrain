# TESTING.md — Slice 1: Project Scaffold

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
