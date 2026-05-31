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

## Earlier slices

| Slice | Test file | Key behaviour |
|-------|-----------|---------------|
| 1 | `test_spine_types.py` | Pydantic models, validators |
| 2 | `test_ingestion.py` | BusinessEvent → MemoryRecord write |
| 3 | `test_worker.py` | Celery reflection hook fires after memory write |
| 4 | `test_agent.py` | AgentRegistry routing, AccountAgent draft, Orchestrator, scope isolation |
| 5 | `test_tools.py` | Tool registry, executor, commitment gate, T3 park |
| 6 | `test_approvals.py` | Approval Queue FastAPI endpoints (approve/edit/reject) |
