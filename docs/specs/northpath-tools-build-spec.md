# Northpath — Tools / Integrations Build Spec

*Applied output of the tools-discovery skill (engine + consulting pack) for the synthetic client "Northpath." Decisions, not code; stops at the tools-subsystem interface. Hands off to: the agents layer (which calls these tools), mission control (which renders the approval contract), and observability (which logs every action and tunes tiers). Reuses the connectors from the ingestion spec and the scope model from the memory spec.*

## 1. Overview

Northpath is a ~30-person operations/strategy **consulting** firm, Google Workspace shop. Stack: Gmail, Google Calendar, Drive/Docs, HubSpot (CRM), Asana (projects), Slack (comms), QuickBooks Online (accounting), Harvest (time + billing). Entities: **Client, Contact, Employee, Engagement.** This subsystem is the **action surface + live-query path** — the "hands." It is the counterpart to ingestion (listen vs. act) and it absorbs the memory layer's `live.query` as its read face.

## 2. Per-system tool catalog

Read tools (all Tier 0, the `live.query` surface): HubSpot deal/contact/company state; Gmail thread read + search; Calendar availability/meeting read; Drive/Docs read + search; Asana task/project/status read; QuickBooks invoice/AR/days-to-pay read; Harvest time/budget/actuals read.

Write tools, by system: HubSpot — log activity, create/update task, move deal stage, mark won/lost. Gmail — draft, send internal, send client. Calendar — private hold, reschedule internal, reschedule/invite incl. client. Drive — create/edit internal doc, share/grant access. Asana — create/update/complete/reassign task, client-visible status post. Slack — internal post, colleague DM, client-channel post. QuickBooks — draft invoice, issue/send invoice, pay bill, run payroll. Harvest — log billable time, post budget-threshold note.

## 3. Autonomy ladder, calibrated

Defaults are conservative (client-facing + money lean to approval); the four axes — reversibility, blast radius, audience, data sensitivity — are the rationale. Northpath's tuned line:

| Tool | Default tier | Northpath setting | Why |
|---|---|---|---|
| All reads | 0 | 0 | changes nothing |
| Draft email, internal doc/task, memory write, calendar hold, log HubSpot activity | 1 | 1 | internal, reversible, low blast radius |
| Reschedule internal-only meeting, internal Slack post | 2 | 2 | autonomous + surfaced, undo window |
| **Reschedule client meeting** | 3 | **3 (draft-and-approve), toggleable** | reaches a client; user wants the option to relax later |
| **Routine client email reply** | 3 | **autonomous *unless commitment-gate trips*** | audience alone ≠ stakes; content stakes decide |
| **Log billable time (Harvest)** | 3 | **autonomous** | money-adjacent but internal & correctable; revisit via observability |
| Issue/send invoice, move deal won/lost, share doc externally, client-channel post, client-visible Asana status | 3 | 3 | external / money-in / reputational |

All overrides live in a **per-client autonomy config** (data, not code) layered over the engine defaults, so engine upgrades propagate without stomping Northpath's tuning.

## 4. The ceiling

**Tier 4 — prepare-only (harness preps 100%, a human executes in the native system):**
- Paying a bill / running payroll in QuickBooks (money out — irreversible, top fraud/error target). Distinct from *issuing* an invoice, which is Tier 3.
- Signing / countersigning an engagement letter or contract (partner authority).

**Off-surface (never built — archive instead):** hard-deleting a Client or Engagement record. The harness soft-deletes / supersedes-with-date, consistent with memory's supersede rule and ingestion's nothing-lost guarantee.

## 5. Tool abstraction + registry

Each tool is a typed, declared capability: `name`, `inputs` schema, `system`, `mode` (read|write), `tier` (default, client-overridable), `scope_required`, `reversible` + `undo` handle, `side_effects`. Agents discover and call only through the registry; the schema makes every call validatable.

## 6. Scope enforcement

Reuse the unified RBAC from memory. Every call carries the caller's scope; the tool inherits the calling agent's scope, which inherits the principal's; sub-agents never act past their principal. Enforced in the tool layer before any connector call. Four scope levels: org / team-practice / entity-client / user-private.

## 7. Execution backbone

- **Idempotency** — every write carries a stable action key; retries/double-dispatch execute once (mirror of ingestion event-idempotency).
- **Preview/dry-run** — write tools return "what would happen"; this is the substrate for approval cards and agent self-check.
- **Retries** — backoff on transient failure (safe because idempotent).
- **Failure & partial success** — never silently dropped; surfaced to the calling agent with detail; every attempt logged.
- **Audit** — every action (attempt, result, approver) → observability.

## 8. HITL approval contract

A Tier-3 call does not execute; it emits a parked request `{ action, preview, requesting_agent, principal, scope, rationale, idempotency_key }` and suspends. Approval → resume + execute (key intact, so resume can't double-fire). Rejection → return to agent with reason. Tools owns this contract; **mission control builds the cockpit** that renders and resolves it.

## 9. Undo windows

Tier-2 tools (internal meeting reschedule, internal Slack post) register an undo handle + short window; the surfaced notification offers one-tap reverse. Tools whose system can't truly undo are not Tier-2-eligible — they're Tier 3.

## 10. Commitment-gate

Runs on outbound **client email** only. Cheap classifier: does this commit Northpath to scope, fees, dates, deliverables, or staffing? No → send autonomously. Yes → escalate to Tier 3. This is the one sanctioned per-call spend — it's how the firm feels the assistant distinguishing "Thursday works" from "we'll deliver the audit by the 15th at the quoted price."

## 11. Read-path / live-query

`live.query(system, field, entity_ref)` is the Tier-0 read subset. Results may be cached in working memory for the task duration only, never promoted to long-term stores. The orchestrator fuses live reads with `recall()`; the code boundary stays explicit (the rule established in the memory spec).

## 12. Observability loop

Instrument per tool: approval rate, edit-on-approval rate, post-hoc correction rate. Feed back as tier-tuning suggestions (rubber-stamped Tier-3 → suggest demote; frequently-corrected autonomous → suggest promote). First two demote candidates to watch: Harvest time logging and client-meeting reschedule.

## 13. Shared connector map

One connector per system, shared with ingestion (ingestion calls read/webhook methods; tools call action methods). Google-shop endpoints: Gmail, Calendar, Drive. **Microsoft fork:** Outlook/Graph, SharePoint/OneDrive, Teams swap in; HubSpot/QuickBooks/Harvest unchanged. Tools and tiers identical across the fork — only endpoints change.

## 14. Tunables

Per-tool tier overrides (the per-client autonomy config); undo-window lengths; commitment-gate threshold/definition; retry/backoff policy; live-query cache TTL (task-duration default).

## 15. Assumptions & out of scope

Assumes the connectors and auth from the ingestion spec, and the scope model + `live.query`/`recall` boundary from the memory spec. Out of scope here: *which agent decides to call which tool* (agents layer); *how approvals are rendered to humans* (mission control); *how actions are stored/traced* beyond emitting the audit event (observability). This spec stops at the tools-subsystem interface: a registry of typed, tiered, scope-aware tools with a reliable execution backbone and a parked-approval contract.
