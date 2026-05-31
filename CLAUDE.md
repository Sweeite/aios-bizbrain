# AIOS BizBrain — Claude Code context

## What this is

An AI operating system for a professional services firm (Northpath). One instance per client.
The brain watches business events, reasons over memory, and acts — but parks any consequential
action for human approval before it fires.

Three-layer architecture:
- **engine/** — pure business logic, no client/pack references
- **packs/consulting/** — Northpath-specific agent specs, tool catalog, mock connectors
- **config/northpath.py** — client-level overrides (autonomy tiers, etc.)

---

## Quick start

```bash
# Backend
cd backend
pip install -e ".[dev]"          # run once per session if deps missing
pytest tests/ -v                 # 171 tests, all green
uvicorn app.main:app --reload    # http://localhost:8000

# Cockpit
cd cockpit
npm install
npm run dev                      # http://localhost:3000
```

Key env vars in `backend/.env`: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`.

---

## Slice progress

| # | Slice | Status |
|---|-------|--------|
| 1 | Scaffold — monorepo, spine types, Supabase schema | ✅ done |
| 2 | Mock ingestion — deal stalled → episodic memory | ✅ done |
| 3 | Celery + Redis — reflection hook fires after memory write | ✅ done |
| 4 | Account agent — Anthropic API, memory recall + live context | ✅ done |
| 5 | Commitment gate + T3 — draft email parks as approval request | ✅ done |
| 6 | Approval Queue — FastAPI + cockpit UI (approve/edit/reject) | ✅ done |
| 7 | Observability — trace tree, eval labels, immutable audit log | ✅ done |
| 8 | Cockpit — Chat interface (streaming, prompt-kit) | ⬜ next |
| 9 | Cockpit — Home / Today (pending approvals, daily brief) | ⬜ |
| 10 | Consolidation + reconciliation Celery tasks | ⬜ |
| 11 | Full mock connector set — all 8 systems | ⬜ |
| 12 | Remaining agents — Comms, Delivery, Finance | ⬜ |
| 13 | Notification delivery — Resend email + Slack webhook | ⬜ |
| 14 | Cockpit — Activity Feed (recent runs, trace tree drilldown) | ⬜ |
| 15 | Cockpit — Client Profiles | ⬜ |
| 16 | Cockpit — Integrations / Health | ⬜ |
| 17 | Real connector — Gmail (OAuth, Pub/Sub webhook) | ⬜ |
| 18 | Real connectors — HubSpot, Asana, Slack, QuickBooks, Harvest | ⬜ |
| 19 | Cockpit — Memory Browser | ⬜ |
| 20 | Cockpit — Settings (Trust Dial, RBAC) | ⬜ |
| 21 | Cockpit — Audit Log view | ⬜ |
| 22 | Cockpit — Cost & ROI | ⬜ |
| 23 | Boilerplate acceptance test — second client, pack swap | ⬜ |

Next issue to pick up: **#9 (Slice 8 — Chat interface)**

---

## QA plan — staged, not all at the end

### QA-1: After Slice 9 — first browser session
- Open cockpit → Home page loads, pending approvals count correct
- Park a T3 action via `python scripts/prove_slice7.py` → appears in approval queue
- Approve it in the UI → card disappears, eval label written
- Chat: type "what's happening with Northpath?" → agent responds with context

### QA-2: After Slice 16 — full mock cockpit
- Walk every page: Home → Chat → Approvals → Activity Feed → Client Profiles → Integrations
- Drill into a run in Activity Feed → full trace tree visible (memory, agent, tool spans)
- Memory Browser → see episodic records for a client
- Trust Dial → lower a tool's tier → verify it affects the next run
- Audit Log → confirm every approve/reject appears, no delete/edit possible

### QA-3: After Slice 18 — real connectors
- Send a real Gmail with commitment language → deal parks in approval queue
- HubSpot deal stage changes → brain wakes up, drafts nudge
- Approve in cockpit → email draft actually appears in Gmail Drafts

---

## What's built

**Backend (fully tested, 171 tests green)**
- `engine/spine/types.py` — all domain types (Span, Run, AuditRecord, MemoryRecord, ParkedApprovalRequest, AutonomyTier T0–T4, Scope)
- `engine/ingestion/` — BusinessEvent → EntityResolver → MemoryWriter (guardrails: dedup, live-owned field protection, review queue)
- `engine/agent/` — AgentRegistry (declarative routing), Orchestrator (creates Run, emits spans), AccountAgent (Anthropic Sonnet, fused memory+live), SpanEmitter (persists to SpanStore)
- `engine/tools/` — ToolRegistry, ToolExecutor (T0/T1 immediate, T3 park+approve), CommitmentGate, DraftEmailTool
- `engine/observability/` — InMemorySpanStore, InMemoryRunStore, InMemoryAuditStore (immutable — raises on UPDATE/DELETE)
- `engine/worker/` — Celery + Redis, reflect_on_step task (Haiku evaluates agent output)

**API (FastAPI)**
- `GET /approvals` — list pending T3 requests
- `POST /approvals/{key}/approve` — approve (optionally with edited body)
- `POST /approvals/{key}/reject` — reject with reason
- `GET /runs/{run_id}/trace` — full span tree (memory → agent → tool → orchestrator spans)
- `GET /health`

**Cockpit (Next.js) — approval queue UI only so far**
- `/cockpit/approvals` — renders parked requests; approve / edit-then-approve / reject actions wired to API

**Database (Supabase — migrations applied)**
- 12 tables, latest migration: `20250531000001_slice7_observability.sql`
- `audit_log` has RLS append-only policy
- `spans` has `eval_label`, `eval_note` columns

---

## Workflow conventions
- Every slice: write failing tests first (TDD), then implement, then `prove_sliceN.py`
- Test files: `backend/tests/test_*.py` — behavior through public interfaces only, no mocking internals
- Each slice closes its GitHub issue with a comment summarising what was delivered
- `supabase db push` from `backend/` after each migration
- Use `/tdd` skill when building new slices
