# Memory System Build Spec — Northpath Consulting

**Purpose.** This document specifies the memory layer for Northpath's AI business assistant. It is a blueprint: it states *what to build* and *the decisions behind it*, not code. An engineer or Claude Code should be able to implement the memory subsystem from this without reading the design conversation. The agent layer, tools, and ingestion connectors are referenced at their boundaries but specified elsewhere.

---

## 1. Overview

**Business.** Northpath, a ~30-person operations/management consulting firm. Three practice areas; partners own client relationships; consultants deliver; one ops/finance person. Billing is by time and by fixed-fee engagement.

**Stack (systems of record).** Google Workspace (Gmail, Calendar, Drive/Docs); HubSpot (CRM/sales); Asana (project/delivery); Slack (internal comms); QuickBooks Online (invoicing/accounting); Harvest (time tracking + billing).
*Microsoft-shop variant: swap Gmail/Calendar/Drive → Outlook/Exchange/SharePoint/OneDrive and Slack → Teams. HubSpot, QuickBooks, Harvest unchanged. The query/write boundary below is identical; only connector endpoints change.*

**Core principle the whole spec obeys.** Memory is not the system of record. Never store what a live system authoritatively owns; store only derived understanding that no system can hand back. If an employee quit tomorrow, the memory system holds what would otherwise be lost.

---

## 2. Memory stores

### Working memory
Per-task scratchpad held by the orchestrator. Contents: the active request, intermediate results, agent/task state, and **the landing zone for all live-queried data**. Live facts live here and are **never** promoted to long-term stores. Lifecycle: discarded at task end, or distilled into a single episodic record. No durable properties required.

### Entity / profile memory
Durable structured records, one per entity. Entities for Northpath:
- **Client** (company)
- **Contact** (person at a client)
- **Employee** (partner / consultant / ops)
- **Engagement** (project or retainer)

Each record holds stable identity fields plus accumulated synthesis (preferences, patterns, relationship context). Identity fields that also exist in a source system (e.g. a contact's title) carry an "as-of" date and are reconciled against the source on use rather than trusted blindly.

### Semantic memory
Firm-wide knowledge not tied to one entity: pricing approach, delivery methodology, rules ("discounts over 15% need partner approval"). Org-scoped, slow-changing, curated, frequently promoted up from repeated episodes.

### Episodic memory
Append-only, time-stamped event log: "deal X → closed-won," "call with ClientCo summarized," "invoice paid 31 days late." High volume. Substrate for the cross-person awareness effect. **Must** be consolidated (section 9).

### Procedural memory
How-to. Two flavours: firm playbooks ("how we run a discovery phase," "when a client churns, do X") and agent-learned action sequences that succeeded.

---

## 3. Universal memory properties

Stamped on every record in entity, semantic, episodic, and procedural stores (not working memory):

| Property | Meaning | Populated from |
|---|---|---|
| **Provenance** | Origin: which agent, source event, or person | The writing agent / ingestion event |
| **Temporal validity** | "As-of" timestamp + expected lifespan | Write time + type-based default lifespan |
| **Scope** | org / team / client-entity / user-private | Derived from source-system access (section 8) |
| **Confidence** | observed / inferred / stated-once | The reflection hook's assessment |

---

## 4. Systems of record & query/write boundary

For every system: the left column is queried live and **never** memorized; the right column is what the memory system writes.

| System | Query live — authoritative, changing | Write to memory — no source of record / synthesis |
|---|---|---|
| **HubSpot** | deal stage, pipeline value, contact title, owner, last-touch date | why a deal was won/lost; "always stalls at proposal, needs a nudge"; relationship dynamics |
| **Gmail** | message contents and threads | gist of a long negotiation; commitments made; the decision a thread reached |
| **Calendar** | who's meeting whom today, availability | "CFO won't take Monday meetings"; client review cadence |
| **Asana** | task status, due dates, assignees, % complete | "their legal team is the bottleneck — pad timelines"; delivery lessons |
| **Slack** | the current conversation | decision reached in a thread; internal norms |
| **QuickBooks** | invoice status, amount owed, payment date | "pays ~30 days late — plan cash around it" |
| **Harvest** | hours logged this week, budget burn-rate | "discovery phases on this engagement type run ~20% over scope" |

---

## 5. Ingestion sources (events → episodic records)

The ingestion pipeline subscribes to these and writes an episodic record per event (provenance = source system + actor; scope per section 8):

- HubSpot: deal stage change, deal created, deal won/lost.
- Gmail: significant sent/received messages on tracked threads (summarized, not stored verbatim long-term).
- Calendar: meeting occurred (and, if available, transcript/notes arrived).
- Asana: task completed, milestone hit, due-date slip.
- Slack: flagged decisions (not the whole firehose — see tunables).
- QuickBooks: invoice issued, invoice paid (with days-to-pay).
- Harvest: budget-threshold crossings, engagement closeout actuals.

---

## 6. Write logic

**Two mechanisms.**
- **Ingestion pipeline** → writes **episodic** records as events arrive (near-real-time).
- **Post-step reflection hook** in the agent loop → decides whether a completed step yielded anything worth synthesizing into entity / semantic / procedural.

**Five write triggers.**
1. Event ingested → write **episodic**. Automatic.
2. Agent infers a preference/pattern/reason not stated in any system, **above the confidence threshold** → write/update **entity** or **semantic**. Below threshold → store as provisional or hold.
3. Scheduled **consolidation pass** → compress / promote / supersede / expire (section 9).
4. Human explicitly teaches a fact or rule → write **semantic/procedural**, confidence = stated, provenance = that person.
5. Novel action sequence succeeds → write/reinforce **procedural**.

**Three guardrails (checked on every write).**
- Never write anything queryable live (reject writes that duplicate a source-of-truth field).
- Dedupe against existing memory — update in place, don't create duplicates.
- Never persist low-confidence inference as fact (must carry provisional confidence).

---

## 7. Retrieve logic

Per task, the orchestrator routes in order:

1. **Entity present?** → load its profile into working memory. Cheap; default yes.
2. **Need a current fact owned by a source system** (status, amount, date, who)? → **query live.** Never trust memory for it.
3. **Need understanding** (why / pattern / preference)? → retrieve from entity / semantic / episodic.
4. **Need a procedure?** → retrieve procedural.

**Fusion rule.** Live data and memory are combined, not chosen between. Example: "Should I worry about this deal?" → memory ("always stalls at proposal") + live HubSpot ("at proposal 3 weeks") → fused recommendation. All retrieval is filtered by the acting user's scope (section 8).

---

## 8. Scoping & access model

**Four scope levels:** **org** (firm knowledge everyone shares — the source of the "knows everything" effect), **team/practice**, **client-entity** (tied to a client; visible only to people who work that client), **user-private**.

**Derive access from the source systems, not a separate permissions store.** Membership on the HubSpot deal / Asana project / client's Drive folder defines who can read that client's memory. Benefits: no parallel ACL to maintain; self-heals (roll off a client → lose access automatically).

**Retrieval is scope-filtered** by the acting user — "knows everything" means "everything you're entitled to know." Client confidentiality is the hard constraint: one client's memory must never surface in work for another.

**Multi-agent rule.** An agent inherits its principal's scope. A sub-agent must never read past what its principal can see.

**Cross-person awareness ("we both know what happened while you were away")** is an emergent property of shared substrate + scope: two people on the same client share that client's scope, so when one acts, the episodic record lands where the other reads it. No special feature needed — it falls out of correct scoping plus ingestion.

---

## 9. Consolidation

A background process run **outside** the live request loop. Five jobs:

1. **Compress** — many similar episodes → one entity/semantic fact (ten "paid late" events → "pays ~30 days late"); raw episodes then age out.
2. **Promote** — recurring patterns crossing a threshold move episodic → semantic/entity.
3. **Supersede** — newer facts override older; the old one is marked superseded *with its date* (audit trail; not hard-deleted), so the system can answer "true as of when."
4. **Expire / decay** — facts past useful life lose confidence or are archived.
5. **Summarize** — rolling per-client digests that power return-from-leave and pre-meeting briefs.

**Cadence (default, tunable):** light nightly pass + deeper weekly pass + on-demand (before a brief). Rationale: without consolidation, retrieval quality degrades, cost climbs, and contradictions accumulate.

---

## 10. Memory subsystem interface

Memory is a self-contained subsystem the agent layer calls through a narrow interface. Conceptual signatures (illustrative, not final API):

- `recall(entity_ref?, need_type, scope_context) -> memories[]`
  where `need_type ∈ {understanding, pattern, preference, procedure, episodic_history}`. Returns scope-filtered memories. Does **not** return source-of-truth facts — those go through the live-query path.
- `write(record)` — record carries store type, payload, and the four properties; subject to the three guardrails.
- `consolidate(scope?, mode)` — `mode ∈ {nightly, weekly, on_demand}`.
- `summarize(entity_ref, since)` — produces the rolling digest.

Live data is reached through a **separate** path (e.g. `live.query(system, field, entity_ref)`) so the boundary is explicit at the code level: memory calls never return live facts and vice-versa. The orchestrator fuses results from both paths.

---

## 11. Tunable parameters

Ship sane defaults, instrument, and refine from observation (false-writes and missed-writes):

| Parameter | Default | Watch for |
|---|---|---|
| Inference confidence threshold (trigger 2) | conservative | too-high → misses real patterns; too-low → noise/false facts |
| Consolidation cadence | nightly + weekly + on-demand | brief staleness vs. compute cost |
| Promotion threshold (episodes → semantic) | e.g. ~3 corroborating episodes | premature promotion of coincidence |
| Decay/expiry windows (per type) | type-based | stale facts surfacing as current |
| Slack ingestion selectivity | flagged decisions only | firehose noise vs. missed decisions |

---

## 12. Assumptions & out of scope

- **Out of scope here:** the agents themselves, tool definitions, and ingestion connector implementations — referenced only at their interfaces.
- **Assumes** read access to the listed systems and that source-system membership is a usable basis for access derivation.
- **Assumes** episodic volume warrants consolidation from day one (true for a 30-person firm; revisit thresholds with real data).
- Microsoft-suite variant changes connector endpoints only, not the design.
