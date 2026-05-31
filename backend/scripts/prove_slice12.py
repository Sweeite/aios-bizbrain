"""
Slice 12 proof: Comms, Delivery, Finance agents — all 4 agents dispatched correctly.

Usage:
    cd backend
    ANTHROPIC_API_KEY=... python scripts/prove_slice12.py
"""
import os
import sys
from unittest.mock import MagicMock

# Cheap mock client — avoids spending API credits on a proof script
def _mock(text: str, input_tokens: int = 80, output_tokens: int = 40):
    client = MagicMock()
    resp = MagicMock()
    resp.content[0].text = text
    resp.usage.input_tokens = input_tokens
    resp.usage.output_tokens = output_tokens
    client.messages.create.return_value = resp
    return client


def _mock_seq(*texts):
    client = MagicMock()
    resps = []
    for t in texts:
        r = MagicMock()
        r.content[0].text = t
        r.usage.input_tokens = 50
        r.usage.output_tokens = 30
        resps.append(r)
    client.messages.create.side_effect = resps
    return client


def main():
    from engine.agent.registry import AgentRegistry
    from engine.agent.live import LiveQuery
    from engine.agent.span_emitter import SpanEmitter
    from engine.ingestion.memory_writer import MemoryWriter
    from engine.agent.orchestrator import Orchestrator
    from engine.spine.types import Scope, ScopeLevel
    from packs.consulting.agent_specs.roster import CONSULTING_AGENTS

    print("=" * 60)
    print("Slice 12 — Remaining agents proof")
    print("=" * 60)

    def make_orch(client):
        registry = AgentRegistry()
        for spec in CONSULTING_AGENTS:
            registry.register(spec)
        return Orchestrator(
            registry=registry,
            memory_writer=MemoryWriter(),
            live=LiveQuery(),
            anthropic_client=client,
            span_emitter=SpanEmitter(),
        )

    # ── 1. AccountAgent (regression) ─────────────────────────────────────────
    print("\n[1] deal.stage_changed → account-agent")
    r = make_orch(_mock("Dear Northpath, following up on your stalled deal...")).handle(
        "deal.stage_changed", "client-northpath-001"
    )
    assert r.agent_name == "account-agent", f"Expected account-agent, got {r.agent_name}"
    print(f"    ✓ agent_name={r.agent_name!r}  span.actor={r.span.actor!r}")
    print(f"    draft[:80]: {r.draft[:80]!r}")

    # ── 2. DeliveryAgent ─────────────────────────────────────────────────────
    print("\n[2] milestone.hit → delivery-agent")
    r = make_orch(_mock("Phase 2 complete. Budget at 68%. On track.")).handle(
        "milestone.hit", "engagement-northpath-001"
    )
    assert r.agent_name == "delivery-agent", f"Expected delivery-agent, got {r.agent_name}"
    assert r.parked is None, "delivery-agent should never park"
    print(f"    ✓ agent_name={r.agent_name!r}  parked={r.parked}")
    print(f"    draft[:80]: {r.draft[:80]!r}")

    # ── 3. FinanceAgent ──────────────────────────────────────────────────────
    print("\n[3] invoice.paid → finance-agent")
    r = make_orch(_mock("3 invoices overdue. AR at 45 days avg.")).handle(
        "invoice.paid", "org"
    )
    assert r.agent_name == "finance-agent", f"Expected finance-agent, got {r.agent_name}"
    assert r.parked is None, "finance-agent must never park (T4 ceiling)"
    print(f"    ✓ agent_name={r.agent_name!r}  parked={r.parked}")
    print(f"    draft[:80]: {r.draft[:80]!r}")

    # ── 4. CommsAgent — routine reply ─────────────────────────────────────────
    print("\n[4] email.received.significant → comms-agent (routine)")
    orch = make_orch(_mock_seq(
        '{"is_client_substantive": false, "client_ref": null}',
        "Thanks for the heads-up. I'll review and respond shortly.",
    ))
    r = orch.handle(
        "email.received.significant",
        "principal-austin",
        request_scope=Scope(level=ScopeLevel.user_private, user_ref="principal-austin"),
    )
    assert r.agent_name == "comms-agent", f"Expected comms-agent, got {r.agent_name}"
    print(f"    ✓ agent_name={r.agent_name!r}  span.scope.level={r.span.scope.level!r}")
    print(f"    draft[:80]: {r.draft[:80]!r}")

    # ── 5. CommsAgent → AccountAgent handoff ─────────────────────────────────
    print("\n[5] email.received.significant + substantive → comms → account-agent handoff")
    orch = make_orch(_mock_seq(
        '{"is_client_substantive": true, "client_ref": "client-northpath-001"}',
        "Dear CFO, thank you for reaching out. Let's discuss the scope expansion.",
    ))
    r = orch.handle(
        "email.received.significant",
        "principal-austin",
        request_scope=Scope(level=ScopeLevel.user_private, user_ref="principal-austin"),
    )
    assert r.agent_name == "account-agent", f"Expected account-agent after handoff, got {r.agent_name}"
    print(f"    ✓ agent_name={r.agent_name!r} (handed off from comms)")
    print(f"    draft[:80]: {r.draft[:80]!r}")

    # ── 6. T4 ceiling — executor attached, parked must be None ───────────────
    print("\n[6] finance-agent + T4 executor → parked=None")
    from engine.tools.registry import ToolRegistry
    from engine.tools.executor import ToolExecutor
    from engine.spine.types import ToolSpec, ToolMode, AutonomyTier

    registry = ToolRegistry()
    for tname in ("quickbooks.pay_bill", "harvest.run_payroll"):
        spec = ToolSpec(
            name=tname, inputs={}, system="test",
            mode=ToolMode.write, tier=AutonomyTier.T4,
            scope_required=ScopeLevel.org, reversible=False, side_effects=[],
        )
        registry.register(spec, lambda inputs, dry_run=False: f"prepare-package:{tname}")

    t4_executor = ToolExecutor(registry)

    from engine.agent.agents.finance import FinanceAgent
    from engine.agent.agents.account import AgentStepResult
    r = FinanceAgent().run(
        entity_ref="org",
        memory_records=[],
        live_context={"ar_ageing_days": 60, "outstanding_invoices": 5},
        scope=Scope(level=ScopeLevel.org),
        run_id="prove-fin-001",
        anthropic_client=_mock("Finance summary with prepare packages."),
        tool_executor=t4_executor,
        idempotency_key="prove-fin-t4-001",
    )
    assert r.parked is None, f"Finance T4 ceiling violated — parked={r.parked}"
    print(f"    ✓ parked={r.parked}  (T4 ceiling holds)")
    print(f"    draft[:80]: {r.draft[:80]!r}")

    print("\n" + "=" * 60)
    print("All assertions passed. Slice 12 proven.")
    print("=" * 60)


if __name__ == "__main__":
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    main()
