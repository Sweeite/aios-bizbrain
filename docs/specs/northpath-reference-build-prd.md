# Reference-Build PRD — Northpath Harness

*Product requirements for the **reference implementation** of the AI business harness, built against the synthetic client "Northpath." This document sits **above** the technical design tier (the master build package + the seven subsystem specs); those answer *how*, this answers *what must be true* and *where the reusable seams are*. It is deliberately complete — the full system, not a phased slice.*

---

## 1. Purpose & framing

This is **not** a product-launch PRD for a company. It is the spec for the **canonical reference build**: the clean, end-to-end implementation of the harness that (a) proves the architecture works across all seven subsystems on a realistic client, and (b) becomes the **boilerplate** every real client is forged from.

Northpath is the synthetic reference client — a ~30-person operations/strategy consulting firm on Google Workspace. We build it once, properly, so that onboarding a *real* client later is **fork the boilerplate → swap the pack → tune the config**, not build from scratch.

**The single most important requirement of this document:** every capability below is labeled by which of three layers it belongs to —

- **[ENGINE]** — identical for every client. The reusable core. Built generic.
- **[PACK]** — vertical-specific (Northpath = the *consulting* pack). Swapped per industry.
- **[CONFIG]** — per-client tuning. Data, not code.

If the engine/pack/config boundary is built cleanly, the result is boilerplate. If it leaks — if Northpath specifics bake into the engine — the result is a one-off that can't be reused. **Preventing that leak is the primary acceptance criterion of the whole reference build.**

---

## 2. What we are building

The complete harness: **seven subsystems over one shared spine**, deployed as a **single instance per client**.

- **Memory** — derived understanding no live system can hand back.
- **Ingestion** — the senses; captures events across all systems, never misses.
- **Tools** — the hands; acts in systems under a per-action autonomy ladder.
- **Agents + Orchestration** — the workers; reason, decide, call tools, synthesize.
- **Mission Control** — the human cockpit; approve, direct, monitor, intervene.
- **Observability** — the substrate; trace, audit, eval, cost/ROI, self-tune.
- **Shared spine** — the types, stores, and seams that connect all of the above.

**Locked technical decisions (from the master build package):** Python backend; TypeScript cockpit; the spine defined once as Python (Pydantic) models exposed to the cockpit as a documented API contract (no preemptive codegen); one instance per client. Everything in the subsystem specs is language-agnostic — the stack governs only how the spine is expressed.

---

## 3. Goals & non-goals

**Goals**
1. A working harness that runs **end-to-end on Northpath** — every cross-subsystem seam exercised, observably.
2. A **clean three-layer separation** (engine/pack/config) such that the engine carries zero Northpath specifics.
3. A reusable **boilerplate** whose reuse test is met (see §9).
4. Fidelity to the architecture as specified — the spine is the single source of truth for shared types.

**Non-goals**
- Not a polished consumer product; the cockpit prototype is reference UX, not the production UI.
- Not shared-tenant SaaS — isolation is per-instance by design.
- Not a real customer's specifics — Northpath is synthetic on purpose.
- No new architecture invented here; this PRD collects and scopes what the specs already decided.

---

## 4. The three-layer contract (the boilerplate seam map)

This table is the heart of the document. For each subsystem, what is engine vs. pack vs. config. **Build the [ENGINE] column generic; deliver the [PACK] column as a replaceable consulting module; expose the [CONFIG] column as per-client data.**

| Subsystem | [ENGINE] — reusable core | [PACK] — consulting (swap per vertical) | [CONFIG] — per-client (tune as data) |
|---|---|---|---|
| **Memory** | 5 stores; 4 universal properties; live-vs-memory query/write boundary; recall/write/consolidate/summarize interface; 3 write guardrails; 5 write triggers; consolidation jobs; scope model | entity types (Client/Contact/Employee/Engagement); the per-system query-vs-memorize table; seed semantic facts | inference confidence threshold; consolidation cadence; promotion threshold; decay windows; Slack selectivity |
| **Ingestion** | BusinessEvent envelope; push+reconciliation backbone; durable queue; idempotency; entity resolution + scope-at-capture; hot-path/deferred split; reflection-hook handoff | per-system acquisition map; event taxonomy; meeting/transcript handling; significance rules | reconciliation cadence; significance thresholds; resolution confidence; backfill window |
| **Tools** | autonomy ladder T0–T4 + off-surface; tier-derivation axes; tool registry + typed schema; scope enforcement; idempotency; preview/dry-run; HITL parked-approval contract; undo windows; failure semantics; commitment-gate pattern | tool catalog per system + default tiers; the Tier-4 ceiling set; the "commitment" definition | per-tool tier overrides; undo-window lengths; commitment-gate threshold; retry policy |
| **Agents + Orch.** | agent definition; earned-boundary test; registry + spec schema; capability routing; thin hierarchical orchestrator; standing/ephemeral split; 2 wake triggers; per-step tiering; inherit-never-exceed; the agent loop (w/ reflection hook) | seed roster (Comms/Account/Delivery/Finance); per-role toolsets; playbooks; proactive triggers | roster edits; model-tier assignments; wake-trigger thresholds |
| **Mission Control** | **all of it** — approval queue, direction surface, monitor/interrupt, trust dial, urgency routing, delegation model (renders, doesn't decide) | *(none — no pack by design)* | delegation policy; urgency→channel routing; notification prefs |
| **Observability** | one stream/four lenses; run/trace tree; span schema; audit projection; approvals-as-labels; cost attribution; self-improvement loop | outcome/ROI definitions; retention norms | retention windows; eval cadence; sampling rates |
| **Spine** | all shared types; data model; cross-subsystem seams | which entities/outcomes are instantiated | per-instance settings |

---

## 5. Functional requirements — by subsystem (complete)

Requirements language: **MUST** = required for the reference build. Layer tags as in §4.

### 5.1 Memory
- MUST implement five stores — working, entity/profile, semantic, episodic, procedural. **[ENGINE]**
- MUST stamp every durable record with the four properties: provenance, temporal validity, scope, confidence. **[ENGINE]**
- MUST enforce the boundary: never memorize what a live system authoritatively owns; reach those via the separate live-query path. **[ENGINE]**
- MUST expose `recall()`, `write()`, `consolidate()`, `summarize()`; live data via a separate `live.query()`; the orchestrator fuses, never chooses. **[ENGINE]**
- MUST apply the three write guardrails (no live-owned fields; dedupe-in-place; no low-confidence-as-fact) and the five write triggers. **[ENGINE]**
- MUST run consolidation (compress/promote/supersede/expire/summarize) outside the request loop. **[ENGINE]**
- MUST instantiate the Northpath entity set and the per-system query-vs-memorize table. **[PACK]**
- MUST read thresholds/cadences/windows from config. **[CONFIG]**

### 5.2 Ingestion
- MUST normalize every source payload to the BusinessEvent envelope. **[ENGINE]**
- MUST guarantee "nothing missed" via durable queue + idempotency + reconciliation sweep (not webhooks alone), with backfill at onboarding. **[ENGINE]**
- MUST resolve entities with confidence and stamp scope at the moment of capture. **[ENGINE]**
- MUST split processing: cheap classify-and-write on the hot path; defer synthesis to the reflection hook. **[ENGINE]**
- MUST write episodic records via `memory.write()` and enqueue the reflection hook; MUST NOT write entity/semantic/procedural directly. **[ENGINE]**
- MUST implement the Northpath acquisition map (HubSpot/Gmail/Calendar/Asana/Slack push; QuickBooks/Harvest poll; transcript source), event taxonomy, and meeting-transcript path. **[PACK]**
- MUST read cadence/thresholds/windows from config. **[CONFIG]**

### 5.3 Tools
- MUST implement the five-tier autonomy ladder + off-surface, with tier derived from the four axes. **[ENGINE]**
- MUST hold tools as typed registry records; MUST enforce scope at call time; MUST make writes idempotent; MUST support preview/dry-run. **[ENGINE]**
- MUST implement the HITL parked-approval contract (emit ParkedApprovalRequest on T3, suspend, resume-on-approve with key intact, return-on-reject). **[ENGINE]**
- MUST implement Tier-4 as prepare-only (harness readies, human executes) and treat hard-delete as off-surface (archive instead). **[ENGINE]**
- MUST implement the commitment-gate as a reusable pattern on outbound client email. **[ENGINE]**
- MUST instantiate the Northpath tool catalog with default tiers, the Tier-4 ceiling (money-out, signing), and the consulting "commitment" definition. **[PACK]**
- MUST read per-tool tier overrides and gate thresholds from the autonomy config. **[CONFIG]**

### 5.4 Agents + Orchestration
- MUST represent agents as declarable specs in a registry; MUST route by capability + scope (no hardcoded identity); MUST keep the orchestrator thin and hierarchical (no peer-to-peer). **[ENGINE]**
- MUST support standing and ephemeral agents; MUST implement the agent loop housing the reflection hook; MUST support per-agent and per-step model tiering. **[ENGINE]**
- MUST support both wake triggers (human-directed and event-driven/proactive). **[ENGINE]**
- MUST enforce inherit-never-exceed on spawned/registered agents. **[ENGINE]**
- MUST ship the Northpath seed roster (Comms/Account/Delivery/Finance) with toolsets, playbooks, and proactive triggers. **[PACK]**
- MUST allow roster/tier/threshold edits as config. **[CONFIG]**

### 5.5 Mission Control
- MUST provide the approval queue (preview-first; edit-then-approve; reject-with-reason; resume-on-approve). **[ENGINE]**
- MUST provide the direction surface (intent → orchestrator → capability routing). **[ENGINE]**
- MUST provide monitor + interrupt (checkpoint-safe; in-flight work parks, not corrupts). **[ENGINE]**
- MUST provide the trust dial (render observability's tier suggestions; accept → write autonomy config). **[ENGINE]**
- MUST route urgency stamped by the emitter (cockpit routes, doesn't decide). **[ENGINE]**
- MUST implement the delegation-during-absence model (scope-bound; Tier-4 never delegates). **[ENGINE]**
- Holds **no pack**. Delegation policy, urgency channels, notification prefs are **[CONFIG]**.

### 5.6 Observability
- MUST implement one event stream with four lenses (telemetry/audit/evals/cost-ROI). **[ENGINE]**
- MUST model runs as trace trees with spans carrying model tier + tokens. **[ENGINE]**
- MUST maintain an immutable, append-only audit projection of action events. **[ENGINE]**
- MUST treat approval-queue actions (approve/edit/reject) as eval labels; MUST support outcome tracking + offline LLM-as-judge runs. **[ENGINE]**
- MUST attribute cost down the trace tree and derive the ROI view; MUST close the self-improvement loop (labels → trust-dial suggestions → autonomy config). **[ENGINE]**
- MUST instantiate the consulting outcome/ROI definitions and retention norms. **[PACK]**
- MUST read retention/eval-cadence/sampling from config. **[CONFIG]**

### 5.7 Shared spine
- MUST define each shared type exactly once (Scope, Entity, BusinessEvent, MemoryRecord, ToolSpec, AutonomyTier, ParkedApprovalRequest, AgentSpec, Run/Span, IdempotencyKey). **[ENGINE]**
- MUST provide the durable stores with their stated guarantees (episodic high-volume; audit immutable; telemetry sampleable; approval queue never silently expires). **[ENGINE]**
- MUST implement all cross-subsystem seams as explicit contracts (§master package §5). **[ENGINE]**
- MUST instantiate Northpath's entity/outcome set. **[PACK]**
- If a subsystem and the spine disagree, the spine wins. **[ENGINE]**

---

## 6. Cross-cutting requirements
- **Identity/access = Scope**, derived from source-system membership; no separate ACL; self-heals on roll-off. Every read and write is scope-filtered. **[ENGINE]**
- **Multi-tenancy = one instance per client**; full data isolation; per-client pack + config. **[ENGINE]** structure, **[CONFIG]** values.
- **Spend posture**, system-wide: lean on mechanical hot paths; generous on felt intelligence (meeting-nuance extraction, agent reasoning/synthesis, client-facing output, LLM-as-judge). Model tier per-agent and per-step; cost attributable down the trace tree so the posture is measurable. **[ENGINE]** mechanism, **[CONFIG]** tier choices.
- **Confidentiality** is the hard constraint: one client's memory must never surface in another's work. **[ENGINE]**

---

## 7. The end-to-end proving path (must run, observably)

The reference build is not "done" until this full chain runs and is visible in the cockpit + observability:

**A HubSpot deal stalls → ingestion captures the event (scoped) → memory recognizes the client's stall pattern → the Account agent (woken proactively) drafts a nudge → the draft routes through the commitment-gate → it parks as a Tier-3 ParkedApprovalRequest → the partner sees it in Mission Control, edits, approves → the tool resumes (idempotency key intact) and sends → the whole run appears in Observability as a trace tree with per-step cost, and the approval becomes an eval label.**

This single path exercises every subsystem and every seam at least once. The rest of the system (all connectors, the full roster, consolidation, the full eval/ROI suite, the trust dial) MUST also be built per §5 — but this path is the spine-level integration test.

---

## 8. Success metrics (for a reference build, not a product)
- **End-to-end:** the §7 path runs without manual glue between subsystems.
- **Seam coverage:** every cross-subsystem contract in the master package is exercised by at least one real run.
- **Layer cleanliness:** the engine compiles and runs with the Northpath pack removed/replaced by a stub (the engine carries no consulting specifics).
- **Observability:** every action is traced, audited, and costed.
- **Scope integrity:** a cross-client read is impossible by construction (verified).

---

## 9. The boilerplate acceptance test (the real bar)

> **A second client can be stood up by forking the reference build and changing only the [PACK] module and the [CONFIG] values — touching no [ENGINE] code.**

Concretely: swapping the consulting pack for a (stub) creative-agency pack and supplying a new client config MUST yield a running harness for that client without engine edits. If this requires changing engine code, the engine/pack/config boundary has leaked and the reference build is not complete.

---

## 10. Out of scope & assumptions
- **Out of scope:** the production cockpit UI (the prototype is reference only); real customer data; non-Google/Microsoft stacks beyond the documented connector fork; the master harness-discovery skill (separate deliverable — it *generates* packages like this for new clients).
- **Assumes:** the locked stack and spine from the master build package; read/write API access to the listed systems; source-system membership usable as the access basis; a chosen transcript source.
- **Companion documents (hand all to Claude Code):** `northpath-master-build-package.md` (entry point) + the seven `northpath-*-build-spec.md` chapters. This PRD tells Claude Code *what must be true and where the seams are*; those tell it *how*.
