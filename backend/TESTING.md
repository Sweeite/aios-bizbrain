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

## Earlier slices

| Slice | Test file | Key behaviour |
|-------|-----------|---------------|
| 1 | `test_spine_types.py` | Pydantic models, validators |
| 2 | `test_ingestion.py` | BusinessEvent → MemoryRecord write |
| 3 | `test_worker.py` | Celery reflection hook fires after memory write |
| 4 | `test_agent.py` | AgentRegistry routing, AccountAgent draft, Orchestrator, scope isolation |
| 5 | `test_tools.py` | Tool registry, executor, commitment gate, T3 park |
