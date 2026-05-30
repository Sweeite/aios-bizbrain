# AIOS BizBrain — Implementation PRD

*Synthesised from the design conversation and Northpath subsystem specs. This is the build specification for the reference implementation — the boilerplate every real client is forged from.*

---

## Problem Statement

Small professional firms — consultancies and agencies — run on knowledge that lives entirely in people's heads. Why a client churned, that this one always pays late, what was really promised on that call, how this engagement type always runs over scope. When a partner is on holiday, a consultant leaves, or someone is simply not in the room, that knowledge is gone and things fall through the cracks. The firm depends on individual memory instead of institutional knowledge, and it shows: missed follow-ups, inconsistent client handling, onboarding that takes months, and a business that stops functioning the moment key people step away.

The tools the firm already runs on — CRM, email, calendar, project management, accounting, chat — each hold a fragment of what happened, but none hold the understanding of *why*, and none talk to each other in a way that produces the full picture a senior partner carries in their head.

---

## Solution

A deployable AI business brain that plugs into every tool a firm already uses and does two things those tools cannot: it remembers how the business actually works, and it acts on the business's behalf.

It captures operational knowledge as it happens — from emails, meetings, deals, deliverables, and financial events — and builds a structured understanding that no single system owns: why deals stall, how this client makes decisions, what commitments were made on that call. It surfaces that understanding proactively to the people who need it, and it handles routine work autonomously while routing anything consequential through a human for approval.

The result is a firm that stops depending on any one person's memory. A partner can take a seven-week holiday and the business keeps running — the brain knows what is happening and either handles it or queues it for someone with the authority to approve.

The system is built as a reusable boilerplate with a clean three-layer separation: an engine that is identical for every client, a vertical pack that captures industry-specific knowledge (consulting for the reference build), and a per-client config layer that tunes the system without touching code. Standing up a new client is: fork the boilerplate, swap the pack, update the config.

---

## User Stories

### Knowledge Capture

1. As a partner, I want the brain to capture what was decided and committed in every client meeting, so that I never lose context from a call I wasn't on.
2. As a partner, I want the brain to recognise patterns in client behaviour from past events, so that I can act on "this client always stalls at proposal" without having to remember it myself.
3. As a partner, I want the brain to capture the reasoning behind won and lost deals, so that the firm learns from outcomes over time.
4. As a partner, I want the brain to know that a specific client pays late, so that I can plan cash flow without manually tracking their payment history.
5. As a partner, I want the brain to remember what was promised on a client call, so that I never inadvertently over-deliver or miss a commitment.
6. As a consultant, I want the brain to capture lessons learned from each engagement — what ran over scope, what the client's real bottleneck was — so that future engagements benefit from past experience.
7. As a partner returning from leave, I want a brief that covers everything that happened while I was away on any client I own, so that I can be back up to speed in minutes.
8. As a partner, I want the brain to capture decisions made in internal Slack threads, so that firm-level knowledge isn't lost in a chat archive.

### Chat and Query

9. As a partner, I want to ask the brain "what do I need to know before my 3pm call with Acme?" and get a synthesised brief, so that I can prepare in seconds rather than reading through emails and CRM notes.
10. As a partner, I want to ask the brain "what is the current status of the GlobalCo engagement?" and get a fused answer from live project data and accumulated understanding, so that I always have the full picture.
11. As a partner, I want to ask the brain "what do we know about how this client makes decisions?" and get a profile drawn from everything we have experienced with them, so that I can tailor my approach.
12. As a consultant, I want to ask the brain "what has happened on this engagement while I was on another project?" and get a full catch-up, so that I can re-engage without a lengthy handover call.
13. As a partner, I want to give the brain a direction ("chase the Globex invoice") and have it act, so that I do not need to do routine follow-up work myself.
14. As a partner, I want the brain to answer questions by fusing what it knows with live data from the source systems, so that answers are always accurate and current.
15. As a partner, I want the chat interface to stream responses, so that I get useful output immediately rather than waiting for a full answer.

### Approval and Oversight

16. As a partner, I want to see a parked approval request before any client-facing email is sent, so that I can review and edit the draft before it reaches a client.
17. As a partner, I want to see the exact content the brain intends to send — not a summary of intent, but the real draft — so that I am approving the concrete artifact.
18. As a partner, I want to edit a draft before approving it, so that I can adjust tone or content without rejecting and restarting.
19. As a partner, I want to reject an approval request with a reason, so that the brain learns from my correction.
20. As a partner, I want any approved action to execute exactly as previewed — no surprises from the moment I click approve to the moment it happens.
21. As a partner, I want the approval queue to be durable — never losing a parked request even if the system restarts — so that nothing falls through the cracks while I am away from the cockpit.
22. As a partner, I want invoice issuance to require my approval, so that money never leaves or is committed without my sign-off.
23. As a partner, I want paying a bill or running payroll to always require me to execute it in the native system, so that the brain never moves money on my behalf.
24. As a partner on holiday, I want a named delegate to be able to approve actions within their existing scope, so that the business keeps running while I am away without widening anyone's authority.
25. As a partner, I want Tier-4 actions — money-out, signing — to never delegate to anyone, so that the most consequential decisions always wait for me.

### Proactive Agent Behaviour

26. As a partner, I want the brain to notice when a deal has stalled past its normal threshold and proactively draft a nudge, so that I never lose a deal to inaction.
27. As a partner, I want the brain to recognise that this specific client always stalls at proposal and factor that into its reasoning, so that the nudge is well-targeted rather than generic.
28. As a partner, I want the brain to monitor invoice ageing and proactively chase overdue payments, so that AR management does not require my attention unless escalation is needed.
29. As a consultant, I want the brain to flag when an engagement's budget is approaching a threshold, so that I can have a scope conversation before we are over.
30. As a partner, I want the brain to prepare a QBR brief when a quarterly review is approaching, so that I can walk in prepared without spending an afternoon assembling information.
31. As a partner, I want the brain to handle routine client email replies autonomously when there is no commitment involved, so that my inbox does not fill up with acknowledgements I have to write.
32. As a partner, I want the brain to escalate when a client email contains a commitment — scope, fees, dates, staffing — so that I always review anything that binds the firm.

### Cockpit — Home and Navigation

33. As a partner, I want a home screen that shows me my pending approvals, today's meetings with context briefs, and flagged items, so that I know what needs my attention the moment I open the cockpit.
34. As a partner, I want urgent items routed to me via Slack or email when I am not in the cockpit, so that I do not miss time-sensitive requests.
35. As a partner, I want low-urgency approvals to queue in the cockpit without notifying me immediately, so that I am not interrupted for routine items.

### Cockpit — Client Profiles

36. As a partner, I want to open a client profile and see everything the brain knows about that client — relationship context, patterns, recent episodes, current engagement status — so that I always have a complete picture before an interaction.
37. As a consultant, I want client profiles to be scoped — I only see clients I work on — so that confidential information stays appropriately contained.

### Cockpit — Activity Feed

38. As a partner, I want to see what the brain has done recently — what events it ingested, what agents ran, what actions it took — so that I always know what is happening without being overwhelmed.
39. As a partner, I want to drill into any activity item and see the full trace — what the agent saw, what it reasoned, what it did — so that I can understand exactly why the brain acted as it did.

### Cockpit — Integrations and Health

40. As an operator, I want to see the health of every connected system — last sync time, connector status, any authentication failures — so that I know immediately if the brain has gone silent on a system.
41. As an operator, I want to see a clear alert when a webhook has broken or an API key has expired, so that I can fix it before events are missed.
42. As an operator, I want to reconnect a broken integration from the cockpit, so that I do not need to touch the server to restore normal operation.

### Cockpit — Memory Browser

43. As a partner, I want to browse what the brain believes to be true about the firm and its clients — semantic facts, procedural playbooks, entity profiles — so that I can verify and correct its understanding.
44. As a partner, I want to explicitly teach the brain a fact or rule, so that firm knowledge I have in my head gets into the system without waiting for it to be inferred from events.
45. As a partner, I want to see the provenance and confidence of any memory record, so that I know whether a belief was observed, inferred, or stated once.

### Cockpit — Audit Log

46. As a partner, I want an immutable audit log of everything the brain has done — every action, every approver, every outcome — so that I can always answer "what exactly did it do and who approved it?"
47. As a partner, I want the audit log to be filterable by client, agent, and date range, so that I can investigate a specific incident without wading through everything.
48. As a partner, I want the audit log to be permanent — never automatically deleted — so that I can refer back to it for any client dispute or compliance question.

### Cockpit — Settings, Trust Dial, and Access

49. As a partner, I want to see when the brain has been autonomously approved on a Tier-3 action 20 or more times without correction, and choose to make it autonomous, so that the system earns more trust over time.
50. As a partner, I want to see when a type of action has been frequently corrected and choose to demote it to requiring approval, so that I can tighten the reins without touching configuration files.
51. As a partner, I want to see what scope each team member holds — which clients they can see, which actions they can approve — so that access is always visible and auditable.
52. As a partner, I want to configure my delegation settings before going on holiday — who covers, which clients, for how long — so that approvals keep flowing in my absence without expanding anyone's permanent authority.
53. As an operator, I want per-client autonomy overrides to live in a configuration file, not in engine code, so that tuning one client does not risk breaking another.

### Cockpit — Cost and ROI

54. As a partner, I want to see what the brain cost this month — total, broken down by client and by agent — so that I can assess whether the spend is justified.
55. As a partner, I want to see what the brain delivered — autonomous actions taken, meetings captured, deals nudged, invoices chased — alongside cost, so that I have an ROI picture, not just a cost figure.
56. As an operator deploying for a new client, I want cost attribution to work out of the box, so that I can tell a real client exactly what their instance costs to run.

### Boilerplate and Onboarding

57. As an operator onboarding a new client, I want to fork the boilerplate, supply a client config file and a vertical pack, and have a running instance, so that standing up a new client does not require touching engine code.
58. As an operator, I want mocked connectors and real connectors to be interchangeable without changing anything outside the connector layer, so that I can test the full system before any real API credentials exist.
59. As an operator, I want all secrets managed as environment variables in the deployment platform, so that credentials are never in the repository.

---

## Implementation Decisions

### Three-Layer Architecture

The system is divided into three layers that must never leak into each other:

- **Engine** — the reusable core, identical for every client. Contains all subsystem logic, the spine, the execution backbone.
- **Pack** — vertical-specific knowledge. The reference build ships a `consulting` pack containing: entity types (Client, Contact, Employee, Engagement), the event taxonomy, tool catalog with default autonomy tiers, the agent seed roster, and ROI outcome definitions. A new vertical is a new pack — no engine changes.
- **Config** — per-client tunables as data, not code. Autonomy tier overrides, reconciliation cadences, consolidation thresholds, notification routing, delegation policy.

The primary acceptance criterion of the whole build: a second client can be stood up by changing only the pack and config — no engine edits.

### Shared Spine

All types that cross subsystem boundaries are defined exactly once in the spine and never redefined elsewhere. Key types: `Scope`, `Entity`, `BusinessEvent`, `MemoryRecord` (with its four universal properties: provenance, temporal validity, scope, confidence), `ToolSpec`, `AutonomyTier`, `ParkedApprovalRequest`, `AgentSpec`, `Run`/`Span`, `IdempotencyKey`.

If a subsystem and the spine ever disagree, the spine wins.

### Autonomy Ladder

Five tiers govern every tool call:
- **T0** — read, executes freely
- **T1** — safe write (internal, reversible), executes freely
- **T2** — autonomous with notification, short undo window
- **T3** — approve-first, emits a `ParkedApprovalRequest` and suspends until resolved
- **T4** — prepare-only, the brain readies the artifact, a human executes in the native system
- **Off-surface** — never built (e.g. hard-delete records — archive instead)

Default tiers are conservative. Per-client overrides live in the autonomy config. The trust dial in the cockpit writes to that config — it does not touch engine code.

### Connector Abstraction

Every external system integration (HubSpot, Gmail, Calendar, Asana, Slack, QuickBooks, Harvest, Drive) is implemented behind a `BaseConnector` abstract interface. The reference build ships mock connectors for all systems — they implement the same interface as real connectors. Swapping a mock for a real connector is one file; nothing upstream changes. Real connectors are added in Phase 3, starting with Gmail.

### Memory Architecture

Five stores with distinct guarantees: working (ephemeral, per-task), entity/profile (structured records per entity), semantic (firm-wide knowledge, slow-changing), episodic (append-only event log, high volume), procedural (playbooks and learned action sequences).

The live-query boundary is enforced in code: `recall()` never returns source-of-truth facts (current deal stage, invoice balance, task status). Those go through a separate `live.query()` path. The orchestrator fuses both — it never chooses one over the other.

Write guardrails on every memory write: never write what a live system authoritatively owns, deduplicate in place, never persist low-confidence inference as fact.

### Commitment Gate

A lightweight classifier that runs on every outbound client email. Classifies whether the email commits the firm to scope, fees, dates, deliverables, or staffing. No commitment → send autonomously. Commitment detected → escalate to T3 for partner approval. This is the mechanism that makes autonomous client email safe.

### Background Jobs — Celery from Day One

All background work runs through Celery with Redis as the broker — no APScheduler, no FastAPI BackgroundTasks. This includes scheduled jobs (consolidation nightly/weekly, reconciliation sweeps every 4–6 hours, offline evals) and event-triggered jobs (reflection hook after each agent step). The boilerplate must be production-ready; mixing task runners would require refactoring at every real client deployment.

### Observability Wired from Slice One

Every agent step, tool call, and memory operation emits a `Span` into the trace store from the first vertical slice. The cockpit views depend on this data; deferring emission creates a dependency that never gets cleanly paid off. Cost attribution (model tier + tokens on every span) is what makes the cost and ROI views possible.

### One Instance Per Client

No multi-tenancy. Each client deployment gets its own Railway services (backend, cockpit, Celery worker) and its own Supabase project. Client data is physically isolated — one client's memory can never surface in another's work. This is a non-negotiable requirement for consulting and agency clients handling confidential information.

### Database Migrations

Supabase CLI manages all schema migrations (`supabase migration new`, `supabase db push`). Migration files are SQL, version-controlled under `supabase/migrations/`. No Python-managed migration layer (Alembic).

### Stack

- **Backend:** Python 3.11+, FastAPI, Pydantic v2
- **Cockpit:** TypeScript, Next.js (App Router), Tailwind CSS, shadcn/ui, prompt-kit
- **Database:** Supabase — Postgres + pgvector (one project per client)
- **Background jobs:** Celery + Redis
- **Hosting:** Railway (backend, cockpit, Celery worker, Redis)
- **LLM:** Anthropic API — `claude-haiku-4-5` for mechanical/classification work, `claude-sonnet-4-6` for reasoning, synthesis, and client-facing output
- **Migrations:** Supabase CLI

### Build Order (Phased)

**Phase 1 — First vertical slice (proves every seam once):**
Spine types → Supabase schema → mock ingestion (one fixture event: HubSpot deal stalled) → episodic memory write → Account agent reasons and drafts nudge → commitment gate trips → T3 tool parks approval → cockpit renders approval queue → partner approves → tool executes → span emitted to observability. Cockpit ships Home, Chat, and Approval Queue views.

**Phase 2 — Fill out the system:**
Remaining agents (Comms, Delivery, Finance), full mock connector set, consolidation jobs, reconciliation sweeps, full observability lenses, trust dial, Activity Feed, Client Profiles, Notifications, Integrations/Health views.

**Phase 3 — Real API connectors:**
Gmail first (highest demo value), then HubSpot, Asana, Slack, QuickBooks, Harvest. Mock-to-real swap — nothing in engine, agents, memory, or tools changes.

**Phase 4 — Polish and second client:**
Memory Browser, Settings (Trust Dial, RBAC, Delegation), Audit Log, Cost & ROI views. Onboard a second (stub) client to prove the boilerplate seam: pack swap + config only, no engine edits.

---

## Testing Decisions

**What makes a good test:** tests cover external behaviour — what the module does given an input — not how it does it internally. A test that breaks when a private function is renamed is a bad test. A test that breaks when the memory write guardrail allows a duplicate is a good test.

**Backend — pytest, automated, built alongside every vertical slice.**

Modules with test coverage:

- **Spine** — all Pydantic types validate correctly; invalid inputs are rejected at the type boundary
- **Ingestion — processor** — a raw fixture event produces the correct `BusinessEvent` envelope with resolved entities and scope
- **Ingestion — resolver** — entity resolution returns the correct confidence score; low-confidence events route to the review queue
- **Memory — write** — all three guardrails are enforced (no live-owned field, no duplicate, no low-confidence-as-fact)
- **Memory — recall** — scope filtering is enforced; a user cannot retrieve memory outside their scope
- **Memory — live_query boundary** — `recall()` never returns a value that should come from `live.query()`; the code boundary is tested explicitly
- **Tools — executor** — T0/T1/T2 calls execute; T3 calls emit a `ParkedApprovalRequest` and suspend; T4 calls return a prepared artifact without executing
- **Tools — commitment gate** — a sample of commitment-bearing emails are correctly classified; a sample of routine emails pass through
- **Tools — idempotency** — the same action key submitted twice executes once
- **Agents — orchestrator** — a given intent routes to the correct agent by capability and scope
- **Agents — scope enforcement** — a spawned agent cannot access data outside its parent's scope
- **Observability — emitter** — every agent step produces a span with the correct fields; cost fields are populated
- **Observability — audit** — audit records are append-only; existing records cannot be mutated
- **Connector abstraction** — mock and real connectors satisfy the `BaseConnector` interface contract identically

**Cockpit — manual verification via TESTING.md checklist, one per vertical slice.**

Each slice ships a TESTING.md that specifies exactly what to open, what to click, and what the expected result is — no interpretation required. Format: numbered steps, expected vs actual, pass/fail. No Playwright or frontend automation at this stage.

---

## Out of Scope

- Real API connectors in Phase 1 or Phase 2 — all external systems are mocked until Phase 3
- Multi-tenancy — one instance per client, always
- Production cockpit UX design — the reference cockpit is functional, not polished; visual refinement happens after a real client is onboarded
- The master harness-discovery skill — the separate deliverable that profiles a new real client and generates a build package like Northpath; this PRD covers only the reference implementation
- Playwright or automated frontend testing — manual TESTING.md checklists for the cockpit
- Celery migration from APScheduler — Celery is used from day one; no migration path is needed
- Microsoft-stack variant — the specs document the fork (Outlook/Teams/SharePoint swap) but it is not built in the reference implementation

---

## Further Notes

**The boilerplate acceptance test** is the real measure of success: a second client can be stood up by forking the reference build and changing only the pack module and client config — no engine code changes. If this requires touching engine code, the engine/pack/config boundary has leaked and the build is not complete.

**The end-to-end proving path** that must run observably before Phase 1 is considered done: a HubSpot deal stalls → ingestion captures the event (scoped) → memory recognises the client's stall pattern → the Account agent (woken proactively) drafts a nudge → the draft routes through the commitment gate → it parks as a T3 `ParkedApprovalRequest` → the partner sees it in Mission Control, edits, approves → the tool resumes (idempotency key intact) and sends → the whole run appears in Observability as a trace tree with per-step cost, and the approval becomes an eval label.

**Notification delivery** outside the cockpit is handled by Resend (email) and Slack webhooks. Urgency is stamped by the emitting subsystem — the cockpit and notification layer route, they do not decide urgency.

**All secrets** (Anthropic API key, Supabase credentials, Redis URL, connector API keys) are managed as environment variables in Railway. Nothing is committed to the repository. `.env.example` documents all required variables.
