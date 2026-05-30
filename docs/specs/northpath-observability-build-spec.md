# Northpath — Observability Build Spec

*Applied output of the observability-discovery skill (engine + consulting pack) for the synthetic client "Northpath." Decisions, not code. Observability is the CONVERGENCE POINT — every other subsystem already emits into it. Reuses: ingestion events, the Tools action-audit events + tier-tuning signals, the per-agent/per-step Agents events, the Mission Control approval decisions, and the memory scope model. Pairs with mission control (which reads these views out) and the trust dial (which acts on the eval signals). Stops at the observability interface.*

## 1. Overview

Northpath: ~30-person operations/strategy consulting firm, Google Workspace shop. Observability records what the harness did, judges quality, measures cost/ROI, and keeps an immutable audit trail. **Governing principle: one event stream, four lenses** — telemetry, audit, evals, cost/ROI are views over a single durable event stream, not separate pipelines. It is the subsystem the other six were pre-wired to feed.

## 2. Event + span schema

One durable stream. A **run** (human-directed or event-driven) roots a **trace tree**: orchestrator → agents → tool calls → memory ops. Each **span** carries: `run_id, parent_span_id, span_id, actor (agent), op (tool|memory|reason), input_ref, output_ref, start/end, model_tier, token_in/out, scope, status/outcome`. The trace tree is the full causal story of one run.

## 3. Telemetry / tracing

The backbone every other lens consumes. Distributed tracing over the agent system: you can open any run and see which agent did what, which tools fired, which memory was read/written, how long each took, and what each cost. Sampling/expiry allowed on general telemetry (it is not the audit record).

## 4. Audit

Immutable, append-only **projection of the Tools action events** — especially Tier 3/4: who approved (from mission control), what executed, idempotency key, before/after state. Never mutated; retained per policy. Not a separate pipeline — a stronger-guarantee view of action events already emitted.

## 5. Evals

- **Approvals-as-labels (key):** Mission Control approve/edit/reject are labels — clean-approve = positive; edit-then-approve = soft negative (the diff is the correction); reject-with-reason = labeled negative. Free labeled data from the partners' normal workflow.
- **Outcome tracking:** did the stalled-deal nudge move the deal? did the drafted client email get a reply? did the overdue-invoice chase get paid?
- **Offline evals:** golden sets for the standing agents (esp. Account reasoning + commitment-gate classification), run as regression checks; LLM-as-judge for open-ended outputs.

## 6. Cost + ROI

- **Cost (exact, free):** every span carries model_tier + tokens, so cost rolls up the trace tree → per run, per agent, per client/engagement. Answers "what does Northpath cost/month," "is the strong-tier Account reasoning spend justified," "which agent is expensive."
- **ROI (the point):** derived view joining cost with consulting outcomes — deal velocity (stalls cleared, time-in-stage), days-to-pay improved, meeting nuance captured, hours saved (autonomous actions × human-time-equiv), engagement-health catches. **v1:** cost fully built; outcomes tracked for the obvious wins; mature ROI is an evolution. Headline the firm wants: "cost $X this month, saved/created $Y."

## 7. Self-improvement loop

Cockpit labels agents (approve/edit/reject) → observability aggregates labels + approval/edit/correction rates → trust dial (mission control) proposes autonomy-tier changes → accepted → written to the per-client autonomy config (Tools). First Northpath signals to surface: Harvest time-logging correction rate, client-meeting-reschedule approval rate, commitment-gate precision (how often a held email was actually a commitment).

## 8. Scope + retention

Observability data is scope-filtered (reuse memory RBAC): a partner sees runs/audit/cost within their scope; clients aren't cross-visible. Retention tunable: audit retained long (per engagement contract); general telemetry retained short then sampled/expired. (Full multi-tenant isolation → cross-cutting pass.)

## 9. Interfaces (what each subsystem emits / reads)

- **Ingestion →** event-received spans (what woke a proactive run).
- **Tools →** action-audit events (the audit projection) + the tier-tuning raw signals.
- **Agents →** per-agent/per-step spans (cost + outcome).
- **Memory →** read/write spans (recall/live/reflection ops).
- **Mission Control ←** reads history/monitor + cost/ROI views; **→** emits approval decisions (the eval labels) and renders the trust-dial suggestions.

## 10. Spend

Lean hot path (emit/trace/audit = mechanical). One deferred spend: LLM-as-judge offline evals (capable model grading agent output), periodic, never hot-path. Same cheap-hot-path / expensive-deferred line as ingestion.

## 11. Assumptions & out of scope

Assumes the emit points all other subsystems already declared, and the memory scope model. Out of scope: the dashboards/screens that render these views (mission control UX — deferred end-of-project deliverable), and full multi-tenant infrastructure (cross-cutting pass). Stops at the observability interface: one event stream with a run/trace tree, an immutable audit projection, an eval layer fed by approvals + outcomes + offline runs, cost attribution down the trace tree, a vertical ROI view, and the self-improvement loop.
