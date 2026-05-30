# Ingestion Build Spec — Northpath Consulting

**Purpose.** Specifies the ingestion layer (the "senses") for Northpath's AI business assistant. Blueprint, not code. Ingestion is **write-mechanism #1** of the memory layer (see the memory build spec): it captures events across Northpath's systems, normalizes and scopes them, writes episodic records, and hands off to the reflection hook. Reuses the business profile and stack from the memory spec.

---

## 1. Overview

Northpath, ~30-person operations/management consulting firm. Stack: Google Workspace (Gmail, Calendar, Drive), HubSpot, Asana, Slack, QuickBooks Online, Harvest, plus a meeting-transcript source (see §9). *Microsoft-shop fork uses Graph change notifications / Teams / SharePoint; design identical, endpoints differ.*

**Guarantee this layer must deliver:** nothing important is missed — even across a 7-week absence. Delivered by durable queue + idempotency + reconciliation, not by webhooks alone.

**Spend posture:** lean on the high-volume mechanical hot path; generous on deferred synthesis and meeting-nuance extraction (that's the product).

---

## 2. Per-system acquisition map

| System | Mode | Events |
|---|---|---|
| HubSpot | Push (webhooks) + poll backstop | deal stage change, won/lost, contact/company change |
| Gmail | Push (watch + Pub/Sub) + poll backstop | significant messages on tracked threads |
| Calendar | Push (watch) + poll backstop | meeting created/updated/occurred |
| Asana | Push (webhooks) + poll backstop | task complete, milestone, due-date slip |
| Slack | Push (Events API), significance-gated | flagged decisions only |
| QuickBooks Online | Poll (natural slow rate) | invoice issued/paid, days-to-pay |
| Harvest | Poll | budget-threshold crossings, engagement actuals |
| Transcript source (§9) | Per tool | meeting transcript ready |

Rule: prefer push for speed; polling is both the mode for weak-webhook systems and the universal backstop.

---

## 3. `BusinessEvent` envelope + event taxonomy

**Envelope (canonical shape for every event):**
`id` · `source_system` · `event_type` (canonical) · `timestamp` · `actor` (→ provenance) · `entities` (resolved Client/Contact/Engagement refs → scope + profile attachment) · `raw_ref` (pointer to raw payload) · `body` (normalized).

**Event taxonomy (the types that matter for Northpath):** deal stage change / won / lost; significant client email (commitment, escalation, scope change); meeting occurred (+ transcript); task/milestone complete or slipped; invoice issued/paid (with days-to-pay); budget threshold crossed; engagement closeout.

---

## 4. Reliability backbone

- **Durable intake queue** — persist every event on arrival, before processing; at-least-once delivery; nothing lost mid-flight.
- **Idempotency** — dedupe on stable source ID; duplicate/overlapping deliveries write once (shared with the memory dedupe guardrail).
- **Reconciliation sweep** — cursor-based "what changed since checkpoint" per system, diffed against ingested set, to catch webhook misses.
- **Backfill** — bounded history ingest at onboarding so the brain isn't blank day one.

---

## 5. Reconciliation cadence

Aggressive, tiered, cheap-by-default (cost scales with misses, not frequency; sweeps are shallow/delta-only):
- Webhook systems (HubSpot, Gmail, Calendar, Slack, Asana): shallow cursor sweep every 4–6h.
- Poll systems (QuickBooks, Harvest): reconcile on each poll at the data's natural rate.
- One deep wide-window sweep daily, off-peak.
- **Gap-triggered:** detected inconsistency (reply with no original, stage jump with no intermediate event) → immediate targeted sweep.
- **Observability-tuned:** track how much reconciliation catches beyond webhooks; near-zero → relax; spiking → a webhook broke.

---

## 6. Entity resolution + scope-at-capture

- Resolve incoming emails/IDs/names to Northpath entity records (Client/Contact/Engagement) with a **confidence** score. High-confidence → attach; low-confidence → small human review queue (don't guess).
- **Stamp scope at capture:** the moment entities resolve, tag the event's scope (which client/team/user), so RBAC/memory-scoping holds from the first instant. (Unified RBAC = memory scoping.)

---

## 7. Processing depth

- **Hot path (every event, cheap):** classify significance + identify entities, write the episodic record, attach entities + scope. Rules or cheap model tier — high-volume mechanical work.
- **Deferred (async, generous):** reflection hook + consolidation handle profile updates, pattern detection, and synthesis. Spend here. The hot-path/deferred line is the cheap-model/strong-model line.

---

## 8. Significance filtering

Cheap gate before anything becomes memory. High signal: client emails with commitments/escalations, meeting outcomes, deal movement, payment behaviour, budget slippage. Low signal: internal Slack chatter (gate to flagged decisions), routine task churn.

---

## 9. Special sources — meetings/transcripts

Highest-value source for Northpath (client meetings carry decision rationale and stakeholder nuance — the core of consulting memory). Calendar provides only that a meeting happened; a transcript source (Otter/Fireflies/Granola/Meet) provides content. Meetings are a **first-class event type** with their own path. **Extraction uses a capable model** (decisions, commitments, stakeholder signals, action items); cost control is storing the distilled output, not re-reading raw transcripts. **Build flag:** recording/transcription consent varies by region — Northpath must handle consent per engagement.

---

## 10. Interface to memory

Ingestion calls the memory subsystem's `write(record)` path to create **episodic** records (carrying the four properties — provenance from `actor`, temporal validity from `timestamp`, scope from resolution, confidence from the classifier) and enqueues the **reflection hook** for deferred synthesis. Ingestion never writes entity/semantic/procedural memory directly — that's the reflection hook's job.

---

## 11. Tunables

Reconciliation cadence (per tier); significance thresholds (per source; Slack gated tightest); entity-resolution confidence threshold; backfill window at onboarding. Ship sane defaults; tune from observability (miss-rate, false-significance rate).

---

## 12. Assumptions & out of scope

- Out of scope: the reflection-hook logic and consolidation (memory spec); tool/action surface (tools spec); connector auth specifics.
- Assumes API access + webhook capability per the acquisition map, and a chosen transcript source.
- Microsoft-suite variant changes endpoints only.
