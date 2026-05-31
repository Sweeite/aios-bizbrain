# TESTING.md — AIOS BizBrain Backend

## Running the test suite

```bash
cd backend
pip install -e ".[dev]"          # install deps if not already done
pytest tests/ -v                 # all slices
pytest tests/test_tools.py -v   # Slice 5 only
```

---

## Slice 5 — Proving path: commitment gate → T3 park → approval_queue row

### Unit tests (automated)

`pytest tests/test_tools.py -v` covers all 8 behavioural cycles:

| Cycle | What it proves |
|-------|----------------|
| 1 | ToolRegistry registers specs and raises ToolNotFound on miss |
| 2 | InsufficientScope raised before any connector call |
| 3 | T0/T1 tools execute immediately and return result |
| 4 | T3 tool returns ParkedApprovalRequest; fn called once (dry_run=True only) |
| 5 | Same idempotency_key submitted twice → parked once, fn called once |
| 6 | CommitmentGate classifies commitment email as T3, routine as T1 |
| 7 | DraftEmailTool.execute returns body; SPEC is T3/write/entity/irreversible |
| 8 | AccountAgent + ToolExecutor → T3 park → ParkedApprovalRequest on result |

### Manual proving path — confirm approval_queue row in Supabase

Requires: Supabase project running, `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` set in `backend/.env`.

**1. Apply the schema** (if not already pushed):

```bash
supabase db push
```

The `approval_queue` table is defined in `supabase/migrations/20250530000001_spine_schema.sql`.

**2. Run the integration script**:

```python
# backend/scripts/test_t3_park.py
import os, uuid
from dotenv import load_dotenv
from supabase import create_client
from engine.spine.types import Scope, ScopeLevel
from engine.tools.registry import ToolRegistry
from engine.tools.executor import ToolExecutor
from engine.tools.implementations.draft_email import DraftEmailTool, SPEC

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

registry = ToolRegistry()
tool = DraftEmailTool()
registry.register(SPEC, tool.execute)
executor = ToolExecutor(registry)

idem_key = f"test-park-{uuid.uuid4()}"
result = executor.execute(
    "gmail.draft_email",
    inputs={
        "to": "northpath@example.com",
        "subject": "Following up on Q3 Audit",
        "body": "Dear Northpath, confirming the Q3 audit engagement at 200 hours commencing June 1.",
    },
    scope=Scope(level=ScopeLevel.entity, entity_ref="client-northpath-001"),
    requesting_agent="account-agent",
    principal="client-northpath-001",
    rationale="commitment email detected",
    idempotency_key=idem_key,
)
print(f"Parked: {result}")

# Persist to Supabase
sb.table("approval_queue").insert({
    "idempotency_key": result.idempotency_key,
    "action": result.action,
    "preview": result.preview,
    "requesting_agent": result.requesting_agent,
    "principal": result.principal,
    "scope_level": result.scope.level.value,
    "scope_entity_ref": result.scope.entity_ref,
    "rationale": result.rationale,
}).execute()
print("Row inserted — verify in Supabase dashboard: Table Editor → approval_queue")
```

```bash
python scripts/test_t3_park.py
```

**3. Verify in Supabase**:

Open **Table Editor → approval_queue**. Confirm:
- `action = "gmail.draft_email"`
- `preview` contains the email body text
- `requesting_agent = "account-agent"`
- `principal = "client-northpath-001"`
- `scope_entity_ref = "client-northpath-001"`
- `status = "pending"`
- `idempotency_key` matches the key printed in the script

**4. Idempotency check** — run the script a second time with the same `idem_key` hardcoded.
Expect: Supabase insert fails with unique-constraint violation on `idempotency_key` (or handle gracefully with ON CONFLICT DO NOTHING).

---

---

## Slice 7 — Observability: trace tree, eval labels, audit log

### Unit tests (automated)

`pytest tests/test_observability.py -v` — 26 behavioural tests across 9 cycles:

| Cycle | What it proves |
|-------|----------------|
| 1 | SpanStore saves and retrieves spans by run_id |
| 2 | RunStore saves and retrieves runs |
| 3 | SpanEmitter persists to SpanStore when store injected |
| 4 | Orchestrator creates Run record, marks done after handle |
| 5 | Orchestrator emits memory-recall span; all spans share one run_id |
| 6 | ToolExecutor emits tool span on approve/reject with correct status |
| 7 | Eval labels: approve=positive, edit-then-approve=soft_negative, reject=negative |
| 8 | Audit records written on approve/reject; InMemoryAuditStore raises on UPDATE/DELETE |
| 9 | GET /runs/{run_id}/trace returns span tree; 404 on unknown run |

### Manual proving path — verify trace tree in Supabase

Requires Supabase project running with `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` set.

**1. Apply the schema migrations:**

```bash
supabase db push
```

New migration `20250531000001_slice7_observability.sql` adds:
- `eval_label TEXT`, `eval_note TEXT` columns on `spans`
- `approver TEXT`, `before_state TEXT`, `after_state TEXT` on `audit_log`
- Row-level security on `audit_log` enforcing append-only

**2. Run the proving path:**

```bash
python scripts/prove_slice6.py   # generates a parked T3 action
```

Then approve via the cockpit or directly:
```bash
curl -X POST http://localhost:8000/approvals/<key>/approve
```

**3. Check the trace tree:**

```bash
curl http://localhost:8000/runs/<run_id>/trace
```

Expected response shape:
```json
{
  "run_id": "...",
  "spans": [
    {"actor": "memory-writer", "op": "memory", "token_in": 0},
    {"actor": "account-agent",  "op": "reason",  "token_in": 120, "token_out": 55},
    {"actor": "tool-executor",  "op": "tool",    "eval_label": "positive"},
    {"actor": "orchestrator",   "op": "reason",  "token_in": 0}
  ]
}
```

**4. Verify in Supabase:**

- **Table Editor → spans**: confirm `eval_label` populated on the tool span.
- **Table Editor → audit_log**: confirm `outcome`, `approver`, `before_state`, `after_state` populated.
- **Immutability check**: attempt `UPDATE audit_log SET outcome = 'modified' WHERE ...` from SQL editor — expect permission denied (RLS policy blocks it).

---

---

## Slice 12 — Remaining agents: Comms, Delivery, Finance

### Unit tests (automated)

`pytest tests/test_slice12_agents.py -v` — 28 behavioural tests across 7 cycles:

| Cycle | What it proves |
|-------|----------------|
| 1 | T4 executor returns prepare artifact (string), never `ParkedApprovalRequest`; fn called with `dry_run=True` only |
| 2 | Orchestrator dispatches by spec name — `milestone.hit` → DeliveryAgent, `invoice.paid` → FinanceAgent |
| 3 | DeliveryAgent produces delivery summary draft; span has correct actor/model/tokens |
| 4 | CommsAgent produces routine reply for non-substantive email; classification uses Haiku |
| 5 | CommsAgent → AccountAgent handoff: substantive client email returns `agent_name == "account-agent"` |
| 6 | FinanceAgent produces prepare-only draft; `result.parked is None` even with T4 executor attached |
| 7 | Full 4-agent routing from CONSULTING_AGENTS roster; catalog has T4 tools; user_private scope resolves for comms |

### Sample prompts / trigger → expected behaviour

| Trigger | entity_ref | Expected agent | Key assertion |
|---------|-----------|---------------|---------------|
| `deal.stage_changed` | `client-northpath-001` | `account-agent` | Draft nudge email; T3 park if executor present |
| `milestone.hit` | `engagement-northpath-001` | `delivery-agent` | Delivery status summary; `result.parked is None` |
| `due_date.slipped` | `engagement-northpath-001` | `delivery-agent` | Scope conversation draft |
| `harvest.budget_threshold_crossed` | `engagement-northpath-001` | `delivery-agent` | Budget alert in draft |
| `invoice.issued` | `org` | `finance-agent` | AR summary; `result.parked is None` even with executor |
| `invoice.paid` | `org` | `finance-agent` | Finance summary with prepare packages |
| `email.received.significant` | `principal-austin` | `comms-agent` (routine) or `account-agent` (handoff) | Routing by LLM classification |
| `human_directed` | any | whichever agent is registered for entity scope | Draft response |

### Comms → Account handoff logic

CommsAgent runs a two-step pattern:
1. **Classify** (Haiku): `{"is_client_substantive": true/false, "client_ref": "<ref>"}`
2. If substantive **and** `client_ref` present → delegates to `AccountAgent`, returns its result
3. If routine (or corrupt JSON) → Sonnet drafts routine reply; `agent_name == "comms-agent"`

### Finance T4 ceiling

`quickbooks.pay_bill` and `harvest.run_payroll` are T4 in the catalog. `ToolExecutor.execute()` for T4 tools:
- Calls `fn(inputs, dry_run=True)` → returns prepare artifact string
- Never creates a `ParkedApprovalRequest`
- Human takes the artifact and executes manually

Verify by running:

```bash
pytest tests/test_slice12_agents.py::TestT4PrepareOnly -v
pytest tests/test_slice12_agents.py::TestFinanceAgent::test_parked_is_none_even_with_t4_executor -v
```

---

## Slice 13 — Notification delivery: Resend email + Slack webhook

### Unit tests (automated)

`pytest tests/test_notifications.py -v` — 14 behavioural tests across 5 cycles:

| Cycle | What it proves |
|-------|----------------|
| 1–2 | High-urgency parks → email + slack both called; routine → neither called |
| 3–4 | Low-urgency → digest queue only; flush clears queue |
| 5 | Router reads `urgent_via` list from config (no hardcoding) |
| 6–7 | `ResendEmailSender` POSTs to `https://api.resend.com/emails`; raises `NotificationError` on non-2xx |
| 8–9 | `SlackWebhookSender` POSTs to `SLACK_WEBHOOK_URL`; raises `NotificationError` on non-2xx |
| 10–11 | ToolExecutor calls `router.route()` on T3 park; existing behaviour unchanged without router |
| 12–13 | `send_digest` Celery task registered; formats items and calls email sender |

### Triggering a high-urgency notification (manual)

**Prerequisites:**
1. Set env vars in `backend/.env`:
   ```
   RESEND_API_KEY=re_<your-key>
   NOTIFICATION_EMAIL_FROM=ai-brain@northpath.example.com
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/<T>/<B>/<token>
   ```
2. Run `python scripts/prove_slice13.py` (see below)

**`backend/scripts/prove_slice13.py`:**

```python
import os
from dotenv import load_dotenv
from engine.notifications.router import NotificationRouter
from engine.notifications.senders import ResendEmailSender, SlackWebhookSender
from engine.spine.types import ParkedApprovalRequest, Scope, ScopeLevel, UrgencyLevel

load_dotenv()

config = {
    "urgent_via": ["slack", "email"],
    "routine_via": ["cockpit_queue"],
    "slack_channel_urgent": "#ai-brain-urgent",
    "email_address": os.getenv("DIGEST_EMAIL_ADDRESS", "partners@northpath.example.com"),
    "digest_email_address": os.getenv("DIGEST_EMAIL_ADDRESS", "partners@northpath.example.com"),
}

router = NotificationRouter(config, ResendEmailSender(), SlackWebhookSender())

req = ParkedApprovalRequest(
    action="draft_email.send",
    preview="Dear client, confirming engagement commencing June 1...",
    requesting_agent="comms-agent",
    principal="partner@northpath.example.com",
    scope=Scope(level=ScopeLevel.entity, entity_ref="client-northpath-001"),
    rationale="Client escalation flagged by account agent",
    idempotency_key="prove-slice13-001",
    urgency=UrgencyLevel.high,
)

router.route(req)
print("High-urgency notification dispatched — check your email + Slack channel.")
```

```bash
python scripts/prove_slice13.py
```

**Expected outcomes:**
- **Resend**: email arrives at `DIGEST_EMAIL_ADDRESS` with subject `[Urgent] Approval required: draft_email.send`
- **Slack**: message appears in the configured incoming webhook destination with the approval preview text

### Verifying the digest task

To manually trigger a digest send (skips the cron schedule):

```bash
cd backend
python -c "
from engine.worker.tasks.notifications import send_digest
from engine.notifications.senders import ResendEmailSender
send_digest(
    items=[{'action': 'asana.create_task', 'preview': 'Create follow-up task', 'requesting_agent': 'delivery-agent', 'idempotency_key': 'k1', 'urgency': 'low'}],
    to_address='partners@northpath.example.com',
)
print('Digest queued — check Celery worker logs and email.')
"
```

Note: This calls the task function directly (bypasses Celery broker). To test via the full Celery pipeline:

```bash
celery -A engine.worker.celery_app worker --loglevel=info &
celery -A engine.worker.celery_app beat --loglevel=info &
# Wait for 07:00 or manually .apply_async() the task
```

---

## Slice 14 — Activity Feed: recent runs + trace drilldown

### Unit tests (automated)

`pytest tests/test_activity.py -v` — 19 behavioural tests across 5 cycles:

| Cycle | What it proves |
|-------|----------------|
| 1 | RunStore.list() returns all runs in reverse chronological order |
| 2 | RunStore.list(scope_entity_ref=) filters by entity scope |
| 3 | GET /activity returns run summaries with trigger, trigger_type, primary_agent, outcome, started_at |
| 4 | GET /activity?scope= filters to matching entity runs only |
| 5 | primary_agent derived from first non-infra reason span; null when no spans |

### Proving path (no server required)

```bash
cd backend
python3 scripts/prove_slice14.py
```

Expected: all PASS, prints span tree for the run with memory-writer / account-agent / orchestrator actors.

### Manual browser test

```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload

# Terminal 2
cd cockpit && npm run dev
```

1. Open `http://localhost:3000/cockpit/activity`
2. Confirm "Activity" appears in the sidebar nav
3. Confirm the page loads with an empty-state card ("No runs yet")
4. The feed is in-memory — no runs appear until an orchestrator run is wired through the live server (comes with real connectors in Slice 17+)

---

## Slice 15 — Client Profiles

### Unit tests (automated)

`pytest tests/test_clients.py -v` — 19 behavioural tests across 5 cycles:

| Cycle | What it proves |
|-------|----------------|
| 1 | GET /clients returns 200 with a list |
| 2 | List items have id, name, deal_stage; Northpath shows Proposal from HubSpot |
| 3 | GET /clients/{id} returns 200 with profile; 404 for unknown client |
| 4 | Profile has brain_understanding (entity_facts + episodic_history) with populated records; live_status has deal, budget, open_tasks, invoices |
| 5 | Scope filter: entity-scoped list returns only matching client; mismatched scope on detail returns 403 |

### Proving path (no server required)

```bash
cd backend
python3 scripts/prove_slice15.py
```

Expected: all PASS — 3 clients, scoped filtering, northpath deal from HubSpot, meridian budget + invoice, scope enforcement.

### Manual browser test

```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload

# Terminal 2
cd cockpit && npm run dev
```

1. Open `http://localhost:3000/cockpit/clients`
2. Confirm "Clients" appears in the sidebar nav
3. Confirm the list shows Northpath (Proposal badge), Meridian Capital, Vertex Partners
4. Click Northpath → detail page shows:
   - **Live Status**: deal (Northpath Q3 Audit, Proposal, 21d), Harvest engagement closed
   - **Brain Understanding**: episodic history with HubSpot + Asana + Harvest events
5. Click Meridian → live status shows budget at 80% threshold, INV-007 open invoice
6. Click Vertex → live status shows slipped Asana task and INV-006 paid invoice
7. Confirm episodic records clearly labelled with confidence level and source provenance

---

## Earlier slices

| Slice | Test file | Key behaviour |
|-------|-----------|---------------|
| 1 | `test_spine_types.py` | Pydantic models, validators |
| 2 | `test_ingestion.py` | BusinessEvent → MemoryRecord write |
| 3 | `test_worker.py` | Celery reflection hook fires after memory write |
| 4 | `test_agent.py` | AgentRegistry routing, AccountAgent draft, Orchestrator, scope isolation |
| 5 | `test_tools.py` | Tool registry, executor, commitment gate, T3 park |
| 6 | `test_approvals.py` | Approval Queue FastAPI endpoints (approve/edit/reject) |
