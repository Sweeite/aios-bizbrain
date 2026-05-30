# Northpath — Master Build Package (Integration + Shared Spine)

*Output of the cross-cutting integration pass. This is the connective document that turns the seven Northpath subsystem specs into one buildable package. It defines the shared spine (the types every subsystem references, defined once), the data model, the cross-subsystem seams, and the cross-cutting concerns. The seven subsystem specs are its chapters (see §8). This document — and only this document — drops to implementation altitude, and only for the shared spine; the subsystem specs stay at "decisions, not code." Hand this entire package to Claude Code.*

---

## 1. Architecture overview

Northpath's harness is seven subsystems over one shared spine, deployed as a single per-client instance.

```
            ┌─────────────── MISSION CONTROL (cockpit, TS) ───────────────┐
            │  approve/edit/reject · direct · monitor/interrupt · trust dial │
            └───────▲───────────────────────▲──────────────────▲───────────┘
                    │ parked approvals       │ direction        │ views + labels
        ┌───────────┴───────────────────────┴──────────────────┴───────────┐
        │                     AGENTS + ORCHESTRATION                         │
        │  thin orchestrator · standing roster + ephemeral · capability route │
        └───▲────────────┬──────────────────────┬───────────────────┬───────┘
            │ events      │ tool calls (tier)    │ recall/live/reflect│ emit
        ┌───┴───┐   ┌─────┴──────┐         ┌─────┴──────┐      ┌──────┴──────┐
        │INGEST │──▶│   TOOLS    │         │   MEMORY   │      │OBSERVABILITY │
        │senses │   │  hands     │         │ understand │      │  substrate   │
        └───┬───┘   └─────┬──────┘         └─────┬──────┘      └──────▲──────┘
            │ write episodic + reflection hook   │                    │
            └────────────────────────────────────┴────────────────────┘
                       all subsystems emit Runs/Spans ─────────────────┘

   one shared SPINE underneath all of it · one instance per client
```

Flow in one line: **ingestion notices → memory understands → agents reason → tools act (gated by tier) → mission control approves what needs a human → observability records, judges, and feeds the trust dial back.** The proactive chain (stalled deal → memory pattern → agent nudge → parked approval) and the self-improvement loop (approvals = labels → trust dial → autonomy config) both fall out of these connections, not new machinery.

---

## 2. Stack + multi-tenancy (locked decisions)

**Stack: Python backend, TypeScript cockpit, one Python-defined spine exposed as a documented API contract.**
- Backend in **Python** — the center of gravity (memory retrieval/embeddings, agent + LLM orchestration, tool-calling loops, evals) is where Python's ecosystem is deepest. The Anthropic SDK is first-class here.
- Cockpit in **TypeScript** — it's a browser app; not a choice.
- The **spine is defined once on the backend** (Pydantic models). The cockpit talks to a **narrow, documented API surface** and hand-writes the thin slice of types it actually renders (approval card, run/monitor view). **No preemptive codegen generator** — it's standing complexity that buys type-sharing with only the lightest subsystem; add it later only if a concrete need appears. Boring and robust over clever.
- *Everything in the seven specs is language-agnostic by construction; the stack changes only how the spine is expressed, not any subsystem decision.*

**Multi-tenancy: one instance per client.** Full data isolation (hard client-confidentiality is a core constraint), per-client config/packs/retention. The shared versioned core absorbs the operational cost. This is the duplicate-repo-but-shared-template model the project assumed throughout.

---

## 3. Shared spine (defined once; referenced everywhere)

Implementation altitude, Pydantic-style. These are the types that cross subsystem boundaries; each is defined here and nowhere else.

**`Scope`** — the central type; the identity/access layer.
`level ∈ {org, team, entity, user_private}` · `entity_ref?` · `team_ref?` · `user_ref?`. **Derived from source-system membership** (HubSpot deal / Asana project / Drive folder), not a separate ACL. Every read and write is scope-filtered; an agent inherits its principal's scope; a sub-agent never exceeds its parent's.

**`Entity`** — `type ∈ {Client, Contact, Employee, Engagement}` · `id` · identity fields (each source-owned field carries an `as_of` date) · `synthesis` (accumulated understanding). Scope attaches to entities; events resolve to them; tools act on them.

**`BusinessEvent`** (ingestion envelope) — `id` · `source_system` · `event_type` (canonical taxonomy) · `timestamp` · `actor` (→ provenance) · `entities[]` (resolved refs → scope) · `raw_ref` · `body` (normalized). Produced by ingestion; consumed by memory (episodic) + observability.

**`MemoryRecord`** — `store ∈ {entity, semantic, episodic, procedural}` · `payload` · **four universal properties**: `provenance`, `temporal_validity` (as_of + lifespan), `scope`, `confidence ∈ {observed, inferred, stated_once}`. Working memory carries none of these (it's ephemeral).

**`ToolSpec`** (registry record) — `name` · `inputs` (schema) · `system` · `mode ∈ {read, write}` · `tier: AutonomyTier` (default, client-overridable) · `scope_required` · `reversible` (+ `undo` handle) · `side_effects`.

**`AutonomyTier`** — `T0 read · T1 safe_write · T2 notify_after · T3 approve_first · T4 prepare_only` + `off_surface` (never built — archive instead). Per-tool default; per-client override lives in the autonomy config (data, not code).

**`ParkedApprovalRequest`** — `action` · `preview` (dry-run output) · `requesting_agent` · `principal` · `scope` · `rationale` · `idempotency_key`. Emitted by tools on a T3 call; rendered/resolved by mission control; resume-on-approve reuses the key so it can't double-fire.

**`AgentSpec`** (registry record) — `name` · `role` · `scope` · `toolset` (subset of the tool registry) · `model_tier` (default + per-step) · `wake_triggers` · `playbooks` (procedural-memory refs) · `spawn_policy` (may it spawn; bounded by inherit-never-exceed).

**`Run` / `Span`** (observability) — Run roots a trace tree. Span: `run_id` · `parent_span_id` · `span_id` · `actor` · `op ∈ {tool, memory, reason}` · `input_ref` · `output_ref` · `start/end` · `model_tier` · `token_in/out` · `scope` · `status/outcome`. Everything emits these.

**`IdempotencyKey`** — the one dedupe discipline shared across ingestion (event dedupe on source ID), tools (action dedupe), and memory (write dedupe).

---

## 4. Data model (durable stores + their guarantees)

| Store | Holds | Guarantee |
|---|---|---|
| Memory: entity/semantic/episodic/procedural | the four MemoryRecord stores | episodic high-volume + consolidated; others curated |
| Durable intake queue + event log | BusinessEvents on arrival | at-least-once; nothing lost mid-flight |
| Tool registry | ToolSpecs | versioned with the engine |
| Agent registry | AgentSpecs | client-editable (data, not code) |
| Autonomy config (per client) | tier overrides | the trust dial writes here |
| Audit log | T3/T4 action records | **immutable, append-only, retained per policy** |
| Telemetry / trace store | Runs/Spans | sampleable / expirable (NOT the audit record) |
| Approval queue | parked T3 requests | durable; never silently expires |

Recommended engine: a relational store (Postgres) for entities/events/registries/audit + a vector index for memory retrieval. Simplest thing that meets the guarantees; revisit only with real volume.

---

## 5. Cross-subsystem contracts (the seams)

Every handoff, explicit, so nothing falls between subsystems:

1. **ingestion → memory:** `memory.write(MemoryRecord{store=episodic, …4 properties})` + enqueue the reflection hook. Ingestion never writes entity/semantic/procedural directly.
2. **agent loop → tools:** call a `ToolSpec`; execution governed by `AutonomyTier` — T0–T2 run, T3 emits a `ParkedApprovalRequest` and suspends, T4 returns a prepared artifact for a human.
3. **tools → mission control → tools:** parked request rendered; approve → resume + execute (idempotency key intact); reject → return to agent with reason.
4. **agent loop → memory:** `recall(need_type, scope)` for understanding; `live.query(system, field, entity_ref)` for source-of-truth facts; reflection hook writes back. Orchestrator **fuses** recall + live (never chooses one).
5. **orchestrator → working memory:** owns the per-task scratchpad + the live-query landing zone (never promoted to long-term).
6. **all → observability:** emit `Run`/`Span` per step (carrying model_tier + tokens → cost attribution).
7. **mission control → autonomy config:** accepted trust-dial suggestions write tier overrides.
8. **observability → mission control:** approval/edit/correction rates → tier-tuning suggestions (the self-improvement loop).

---

## 6. Cross-cutting concerns

- **Identity/access = `Scope`.** No separate permissions store; derived from source-system membership; self-heals (roll off a client → lose access). This is the single access primitive across all seven subsystems.
- **Multi-tenancy = one instance per client** (see §2). Per-client data, config, packs, retention.
- **Engine / pack / client-config — three layers.** Engine = shared versioned core (all subsystem engines + this spine). Pack = vertical (consulting here: entity types, event taxonomy, tool catalog + tiers, agent roster, outcome/ROI defs). Client-config = per-client tuning (autonomy overrides, agent roster edits, tunables, retention). Engine upgrades propagate; client tuning is never stomped.
- **Spend posture, system-wide.** Lean on mechanical hot paths (ingestion classify, tool execution, telemetry emit); generous on the felt intelligence (meeting-nuance extraction, agent reasoning/synthesis, client-facing output, LLM-as-judge evals). Model tier is per-agent and per-step; cost is attributable down the trace tree, so the posture is measurable, not asserted.

---

## 7. Build order for the implementer (Claude Code)

1. **Scaffold the spine** (§3) — the Pydantic types + the per-client instance skeleton.
2. **Stand up the stores** (§4) — Postgres + vector index; the queue; the registries; the audit + trace stores.
3. **Wire the `Scope` model** — derived from source-system membership; prove read/write scope-filtering end-to-end.
4. **Build one vertical slice end-to-end** before breadth: one connector (e.g. HubSpot) → ingestion → episodic memory write → one agent (Account) → one T3 tool (send client email) → parked approval in the cockpit → execute → observability run visible. This exercises every seam once.
5. **Fill out** the remaining connectors, agents, tools, and the consolidation/eval/trust-dial loops.
6. **Layer pack + client-config** so a second client is config, not code.

---

## 8. Index of chapters (the subsystem specs)

This package = this integration document + the seven specs below (each at "decisions, not code" altitude):

1. `northpath-memory-build-spec.md` — the understanding layer; defines Scope, the four properties, recall/live boundary, consolidation.
2. `northpath-ingestion-build-spec.md` — the senses; BusinessEvent, reliability backbone, reconciliation, meetings.
3. `northpath-tools-build-spec.md` — the hands; autonomy ladder, registry, parked-approval contract, commitment-gate.
4. `northpath-agents-build-spec.md` — the workers + orchestration; agent registry, capability routing, wake triggers, inherit-never-exceed.
5. `northpath-mission-control-build-spec.md` — the cockpit; approval queue, direction, monitor/interrupt, trust dial, delegation.
6. `northpath-observability-build-spec.md` — the substrate; one stream/four lenses, audit projection, approvals-as-labels, cost/ROI, the loop.
7. *(orchestration is captured within the agents spec.)*

---

## 9. Assumptions & out of scope

- **Assumes** the stack + multi-tenancy decisions in §2 and the seven specs as written.
- **Out of scope here:** per-subsystem internals (in the chapters); the **master harness-discovery skill** (next deliverable — profiles a new client once and sequences the sub-skills to regenerate a package like this); the **mission-control UX spec / prototype** (final deliverable — screen-level cockpit design, renders §3 types + observability views).
- The spine is the one place these types live; if a subsystem and the spine ever disagree, the spine wins and the subsystem spec is corrected to match.
