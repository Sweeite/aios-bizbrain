# Northpath — Agents + Orchestration Build Spec

*Applied output of the agents-orchestration-discovery skill (engine + consulting pack) for the synthetic client "Northpath." Decisions, not code; stops at the agents-subsystem interface. Reuses: the tool registry + autonomy tiers + parked-approval contract (tools spec), working memory + recall/live.query + reflection hook + scope inheritance (memory spec), and event triggers (ingestion spec). Hands off to: mission control (human direction + approval rendering) and observability (per-agent/per-step logging, cost, evals).*

## 1. Overview

Northpath: ~30-person operations/strategy **consulting** firm, Google Workspace shop. Stack: Gmail, Calendar, Drive/Docs, HubSpot, Asana, Slack, QuickBooks Online, Harvest. Entities: Client, Contact, Employee, Engagement. This subsystem is the **workers + coordination** — the reasoning layer that decides what to do, calls the tools, and synthesizes the answers the firm feels.

## 2. Topology

Hierarchical, **thin orchestrator + standing specialists + ephemeral task agents**. Explicitly **multi-agent but not a swarm**: agents never call each other peer-to-peer; the orchestrator decomposes tasks, delegates, owns the chain of scope and working memory. Multi-agent *by capability* — a simple request may wake only one agent.

## 3. Seed roster

A **seed**, not fixed — all four are registry specs the client can edit or extend.

| Agent | Scope | Toolset | Earned because |
|---|---|---|---|
| **Comms / chief-of-staff** | principal's own inbox/calendar/internal comms | Gmail, Calendar, Slack | distinct scope (the principal's own surface), distinct tools, highest-traffic context; commitment-gate runs here |
| **Account / relationship** | per-client + deal state | HubSpot + cross-reads | distinct scope (client relationships), distinct reasoning (stakeholder/deal) |
| **Delivery / project** | per-engagement execution | Asana, Drive | distinct scope (engagement delivery), distinct tools |
| **Finance / billing** | firm financials + budgets | QuickBooks, Harvest | distinct scope (money), distinct tools; holds the Tier-4 ceiling |

Plus the **orchestrator** and **ephemeral task agents** (QBR prep, proposal build, weekly portfolio review, prospect research). Research/analysis is deliberately **ephemeral, not standing** — no durable scope of its own.

Comms↔Account overlap (outbound client email) is resolved by **handoff, not merge**: Comms sends routine mail; drafts touching deal/relationship substance hand to Account.

## 4. Agent spec schema + registry

Each agent is a declarable record: `{ name, role, scope, toolset, model_tier (default + per-step), wake_triggers, playbooks, spawn_policy }`, held in an **agent registry**. Adding or customising an agent = writing/editing a spec — **no orchestrator code changes**. The orchestrator routes by **capability + scope match** against the registry, so a newly registered agent is automatically routable.

## 5. Orchestration

Orchestrator receives the trigger, decomposes, routes, holds working memory, fuses `recall()` with `live.query()`, returns the result. Multi-agent example — "prep the QBR for Acme": orchestrator pulls Account (relationship/deal state), Delivery (engagement status), Finance (budget/AR), composes the brief; specialists do not call each other.

## 6. Wake triggers

- **Human-directed** via mission control.
- **Event-driven (proactive):** ingestion event crosses significance → an agent acts unprompted. Northpath chain: deal stalled at proposal 3 weeks (ingestion) → memory knows this client always stalls at proposal → Account drafts nudge → parks at Tier 3 (tools) → partner approves (mission control). Nobody asked.

## 7. Extensibility + guardrail

"Add agents later," "customise the seed roster," and "the harness spins up agents for new workflows" are **one mechanism**: register a spec. **Guardrail:** a spawned/registered agent inherits and can never exceed its parent's scope and toolset — extensibility is not privilege escalation. (Reuses memory scope inheritance.)

## 8. The agent loop

*perceive → recall()/live.query() → reason → act (call a tool, obey its tier) → reflect (reflection hook writes memory)*. The reflection hook (memory write-mechanism #2) lives here. The orchestrator wraps the loop with working memory and, for multi-agent tasks, decomposition + delegation.

## 9. Model tiering

Per-agent and per-step. **Strong tier:** Account relationship/stakeholder synthesis, pre-meeting briefs, proposal/QBR content, cross-context answers the partners read. **Cheap tier:** routing, significance-gating, status roll-ups, mechanical task creation. This is where the value-justified spend posture is concretely spent.

## 10. Handoffs

Overlaps between genuinely-distinct agents resolved by handoff rules, not merges (Comms→Account on substantive client mail). No peer-to-peer task delegation — handoffs are orchestrator-mediated.

## 11. Interfaces

- **Tools:** agents call the tool registry; tier governs execution; Tier-3 parks via the approval contract.
- **Memory:** orchestrator owns working memory + recall/live fusion; reflection hook in the loop writes durable memory; all scope-filtered.
- **Ingestion:** events are the proactive wake trigger.
- **Mission control:** renders human direction and the parked approvals agents generate.
- **Observability:** every agent + step logged with cost and outcome (feeds tier tuning + ROI).

## 12. Assumptions & out of scope

Assumes the tool registry + tiers + approval contract, the memory interfaces + scope model, and ingestion events. Out of scope here: the human cockpit UI (mission control), and logging/eval/cost internals (observability) beyond emitting events. Stops at the agents-subsystem interface: a registry of declarable, scope-bound, tool-granted agents coordinated by a thin hierarchical orchestrator, woken by humans or events, extensible by spec.
