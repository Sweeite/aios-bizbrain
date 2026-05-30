# Northpath — Mission Control Build Spec

*Applied output of the mission-control-discovery skill (engine-only — no vertical packs) for the synthetic client "Northpath." Decisions, not code. This subsystem RENDERS contracts the others emit and holds no business logic. Reuses: the Tier-3 parked-approval contract + preview/dry-run + idempotency (tools spec), the human-direction wake trigger + orchestrator routing + interrupt (agents spec), the scope model (memory spec). Pairs with observability (history views + tuning suggestions). Stops at the mission-control interface.*

## 1. Overview

Northpath: ~30-person operations/strategy consulting firm, Google Workspace shop. Mission control is the **human cockpit** — where a partner approves parked Tier-3 actions, directs the harness, and monitors/intervenes. **Governing principle: it renders, it does not decide.** Autonomy policy lives in Tools; reasoning in Agents; understanding in Memory. The cockpit holds almost no business logic. (UI-heavy subsystem — TypeScript — rendering shared types, above all the parked-approval request.)

## 2. Approval queue (the heart)

Tier-3 parked requests render as cards showing the **preview/dry-run** (already produced by Tools), the agent's **rationale**, and the affected **entity + scope**. Interactions: **preview-first** (approve the concrete artifact — the exact client email, invoice, reschedule — never an abstract intent); **edit-then-approve** (tweak the draft before releasing — the payoff of draft-at-T1/release-at-T3); **reject-with-reason** (returns to the agent with the reason per the contract). On approve, the parked action resumes and executes, idempotency key intact (no double-fire).

Northpath examples flowing through: send client email that tripped the commitment-gate; issue an invoice; move a deal to Closed-Won; reschedule a client meeting; log billable time (if the client keeps it at T3 rather than the autonomous setting).

## 3. Agent direction (command surface)

A command line to the **orchestrator**, not to a named agent. A partner states intent ("prep the Acme QBR", "chase the overdue Globex invoice"); the orchestrator decomposes and routes by capability. The partner never needs to know the roster.

## 4. Monitor + intervene

Live + historical view of what agents are doing (history fed by observability — not rebuilt here). **Interruption at safe checkpoints — between tool calls**: each call is idempotent and atomic, so a hard-stop **parks** in-flight work rather than corrupting it. Reuses the idempotency + parked-state machinery.

## 5. Trust dial (human end of self-calibration)

Observability watches approval / edit / post-hoc-correction rates and *suggests* tier changes; mission control is **where the partner sees and accepts** them ("approved unchanged 20×, make autonomous? [yes]"). The suggestion is rendered here; the accepted change is written to the **per-client autonomy config** (Tools), not stored in the UI. First Northpath suggestions to expect: demote Harvest time-logging confidence, and the client-meeting reschedule toggle.

## 6. Urgency / notifications

**Render-don't-decide:** the emitting subsystem (agent/tool) stamps urgency; mission control routes by it to a channel (in-app, email, Slack, push). No urgency logic in the cockpit. Northpath routing: client escalations + overdue-invoice follow-ups → push/Slack now; routine approvals → in-app queue; digests for low-urgency.

## 7. Delegation during absence (the chosen posture)

Northpath default (conservative, scope-clean): while a partner is away, approvals queue and urgent ones **escalate to a named delegate**; the delegate can approve only within **scope they already hold** (a delegate with a given client's scope approves that client's actions, not the whole firm's); **Tier-4 ceiling actions (money-out, signing) never delegate** — they wait for the principal. This makes "7-week holiday, nothing breaks" true without widening anyone's authority. (Configurable: client may choose flatter — any partner approves anything during absence — or stricter — nothing escalates. Data, not structure.)

## 8. Interfaces

- **Tools:** consumes the parked-approval contract `{action, preview, requesting_agent, principal, scope, rationale, idempotency_key}`; approve → resume; reject → return reason; accepted trust-dial changes → autonomy config.
- **Agents / orchestrator:** sends human-directed intents; issues checkpoint interrupts.
- **Memory:** reads the scope model for delegation eligibility.
- **Observability:** renders history + monitor views; renders and routes tier-tuning suggestions.
- **Shared spine:** renders shared types; redefines none.

## 9. Stack note

TypeScript UI. The approval card renders the parked-request type defined once in the shared spine; the monitor view renders observability event types. Mission control adds presentation + interaction only — no new domain types, no business logic.

## 10. Assumptions & out of scope

Assumes the Tools approval contract + preview, the Agents direction/interrupt seams, the Memory scope model, and observability event/suggestion feeds. Out of scope: the autonomy *policy* itself (Tools), agent *reasoning* (Agents), and observability *internals* (logging/eval/cost). Stops at the mission-control interface: a preview-first approval queue, an orchestrator-routed direction surface, a checkpoint-safe monitor/interrupt surface, the trust-dial tuning surface, urgency routing, and a scope-bound delegation model — all rendering, none deciding.
