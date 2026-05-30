"""
Spine type validation tests.
Each test describes observable behavior through the public Pydantic interface.
"""
import pytest
from pydantic import ValidationError

from engine.spine.types import (
    Scope, ScopeLevel,
    Entity, EntityType,
    BusinessEvent,
    MemoryRecord, MemoryStore, Confidence,
    ToolSpec, ToolMode,
    AutonomyTier,
    ParkedApprovalRequest,
    AgentSpec,
    Run, Span, SpanOp,
    IdempotencyKey,
)


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------

class TestScope:
    def test_org_scope_requires_no_refs(self):
        s = Scope(level=ScopeLevel.org)
        assert s.level == ScopeLevel.org
        assert s.entity_ref is None
        assert s.team_ref is None
        assert s.user_ref is None

    def test_entity_scope_requires_entity_ref(self):
        with pytest.raises(ValidationError):
            Scope(level=ScopeLevel.entity)  # missing entity_ref

    def test_entity_scope_with_ref_is_valid(self):
        s = Scope(level=ScopeLevel.entity, entity_ref="client-123")
        assert s.entity_ref == "client-123"

    def test_user_private_scope_requires_user_ref(self):
        with pytest.raises(ValidationError):
            Scope(level=ScopeLevel.user_private)  # missing user_ref

    def test_user_private_scope_with_ref_is_valid(self):
        s = Scope(level=ScopeLevel.user_private, user_ref="user-456")
        assert s.user_ref == "user-456"

    def test_invalid_level_rejected(self):
        with pytest.raises(ValidationError):
            Scope(level="superadmin")


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

class TestEntity:
    def test_client_entity_valid(self):
        e = Entity(
            id="ent-001",
            type=EntityType.client,
            name="Acme Corp",
        )
        assert e.type == EntityType.client
        assert e.synthesis == {}

    def test_entity_type_rejects_unknown(self):
        with pytest.raises(ValidationError):
            Entity(id="x", type="vendor", name="X")

    def test_identity_field_carries_as_of(self):
        from datetime import datetime
        e = Entity(
            id="ent-002",
            type=EntityType.contact,
            name="Jane Doe",
            title="CFO",
            title_as_of=datetime(2024, 1, 1),
        )
        assert e.title == "CFO"
        assert e.title_as_of is not None

    def test_synthesis_accumulates(self):
        e = Entity(
            id="ent-003",
            type=EntityType.engagement,
            name="Q2 Audit",
            synthesis={"stall_pattern": "always at proposal"},
        )
        assert e.synthesis["stall_pattern"] == "always at proposal"


# ---------------------------------------------------------------------------
# BusinessEvent
# ---------------------------------------------------------------------------

class TestBusinessEvent:
    def test_valid_event(self):
        from datetime import datetime, timezone
        ev = BusinessEvent(
            id="evt-001",
            source_system="hubspot",
            event_type="deal.stage_changed",
            timestamp=datetime(2025, 3, 1, 12, 0, tzinfo=timezone.utc),
            actor="hubspot-webhook",
            entities=["client-123"],
            raw_ref="hs-deal-99",
            body={"to_stage": "Proposal"},
        )
        assert ev.source_system == "hubspot"
        assert len(ev.entities) == 1

    def test_event_missing_required_fields_rejected(self):
        with pytest.raises(ValidationError):
            BusinessEvent(source_system="hubspot")  # missing id, event_type, etc.


# ---------------------------------------------------------------------------
# MemoryRecord
# ---------------------------------------------------------------------------

class TestMemoryRecord:
    def test_episodic_record_valid(self):
        from datetime import datetime, timezone
        rec = MemoryRecord(
            store=MemoryStore.episodic,
            payload={"summary": "Deal stalled for 3 weeks"},
            provenance="account-agent",
            temporal_validity={
                "as_of": datetime(2025, 3, 1, tzinfo=timezone.utc).isoformat(),
                "lifespan_days": 90,
            },
            scope=Scope(level=ScopeLevel.entity, entity_ref="client-123"),
            confidence=Confidence.observed,
        )
        assert rec.store == MemoryStore.episodic
        assert rec.confidence == Confidence.observed

    def test_invalid_store_rejected(self):
        with pytest.raises(ValidationError):
            MemoryRecord(
                store="working",  # not a valid durable store
                payload={},
                provenance="x",
                temporal_validity={"as_of": "2025-01-01", "lifespan_days": 1},
                scope=Scope(level=ScopeLevel.org),
                confidence=Confidence.observed,
            )

    def test_invalid_confidence_rejected(self):
        with pytest.raises(ValidationError):
            MemoryRecord(
                store=MemoryStore.semantic,
                payload={},
                provenance="x",
                temporal_validity={"as_of": "2025-01-01", "lifespan_days": 1},
                scope=Scope(level=ScopeLevel.org),
                confidence="certain",  # not a valid confidence level
            )


# ---------------------------------------------------------------------------
# AutonomyTier
# ---------------------------------------------------------------------------

class TestAutonomyTier:
    def test_all_tiers_exist(self):
        assert AutonomyTier.T0 == "T0"
        assert AutonomyTier.T1 == "T1"
        assert AutonomyTier.T2 == "T2"
        assert AutonomyTier.T3 == "T3"
        assert AutonomyTier.T4 == "T4"


# ---------------------------------------------------------------------------
# ToolSpec
# ---------------------------------------------------------------------------

class TestToolSpec:
    def test_read_tool_valid(self):
        ts = ToolSpec(
            name="hubspot.get_deal",
            inputs={"deal_id": "string"},
            system="hubspot",
            mode=ToolMode.read,
            tier=AutonomyTier.T0,
            scope_required=ScopeLevel.entity,
            reversible=True,
            side_effects=[],
        )
        assert ts.mode == ToolMode.read
        assert ts.tier == AutonomyTier.T0

    def test_write_tool_with_undo(self):
        ts = ToolSpec(
            name="gmail.send_email",
            inputs={"to": "string", "body": "string"},
            system="gmail",
            mode=ToolMode.write,
            tier=AutonomyTier.T3,
            scope_required=ScopeLevel.entity,
            reversible=False,
            undo=None,
            side_effects=["email_sent"],
        )
        assert ts.tier == AutonomyTier.T3

    def test_tool_missing_name_rejected(self):
        with pytest.raises(ValidationError):
            ToolSpec(
                inputs={},
                system="x",
                mode=ToolMode.read,
                tier=AutonomyTier.T0,
                scope_required=ScopeLevel.org,
                reversible=True,
                side_effects=[],
            )


# ---------------------------------------------------------------------------
# ParkedApprovalRequest
# ---------------------------------------------------------------------------

class TestParkedApprovalRequest:
    def test_valid_parked_request(self):
        par = ParkedApprovalRequest(
            action="gmail.send_email",
            preview="Hi Acme, following up on the proposal...",
            requesting_agent="account-agent",
            principal="user-partner-1",
            scope=Scope(level=ScopeLevel.entity, entity_ref="client-123"),
            rationale="Deal stalled 3w; nudge per playbook",
            idempotency_key="acct-nudge-client-123-2025-03-01",
        )
        assert par.action == "gmail.send_email"
        assert par.idempotency_key == "acct-nudge-client-123-2025-03-01"

    def test_missing_idempotency_key_rejected(self):
        with pytest.raises(ValidationError):
            ParkedApprovalRequest(
                action="gmail.send_email",
                preview="...",
                requesting_agent="account-agent",
                principal="user-1",
                scope=Scope(level=ScopeLevel.org),
                rationale="...",
                # idempotency_key omitted
            )


# ---------------------------------------------------------------------------
# AgentSpec
# ---------------------------------------------------------------------------

class TestAgentSpec:
    def test_account_agent_spec_valid(self):
        spec = AgentSpec(
            name="account-agent",
            role="Manages client relationships and deal state",
            scope=Scope(level=ScopeLevel.entity, entity_ref="client-123"),
            toolset=["hubspot.get_deal", "gmail.send_email"],
            model_tier={"default": "strong", "routing": "cheap"},
            wake_triggers=["deal.stage_changed", "human_directed"],
            playbooks=["nudge-stalled-deal", "pre-meeting-brief"],
            spawn_policy={"may_spawn": True, "max_depth": 1},
        )
        assert spec.name == "account-agent"
        assert "hubspot.get_deal" in spec.toolset

    def test_agent_spec_missing_name_rejected(self):
        with pytest.raises(ValidationError):
            AgentSpec(
                role="x",
                scope=Scope(level=ScopeLevel.org),
                toolset=[],
                model_tier={},
                wake_triggers=[],
                playbooks=[],
                spawn_policy={},
            )


# ---------------------------------------------------------------------------
# Run / Span
# ---------------------------------------------------------------------------

class TestRunAndSpan:
    def test_run_valid(self):
        from datetime import datetime, timezone
        run = Run(
            run_id="run-001",
            initiated_by="account-agent",
            scope=Scope(level=ScopeLevel.entity, entity_ref="client-123"),
            started_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
        )
        assert run.run_id == "run-001"

    def test_span_valid(self):
        from datetime import datetime, timezone
        span = Span(
            span_id="span-001",
            run_id="run-001",
            parent_span_id=None,
            actor="account-agent",
            op=SpanOp.reason,
            input_ref="memory-recall-001",
            output_ref="draft-nudge-001",
            started_at=datetime(2025, 3, 1, 12, 0, tzinfo=timezone.utc),
            ended_at=datetime(2025, 3, 1, 12, 1, tzinfo=timezone.utc),
            model_tier="strong",
            token_in=500,
            token_out=120,
            scope=Scope(level=ScopeLevel.entity, entity_ref="client-123"),
            status="success",
            outcome="draft_created",
        )
        assert span.op == SpanOp.reason
        assert span.token_in == 500

    def test_span_invalid_op_rejected(self):
        with pytest.raises(ValidationError):
            Span(
                span_id="x",
                run_id="r",
                actor="a",
                op="think",  # invalid op
                input_ref="i",
                output_ref="o",
                started_at="2025-01-01T00:00:00Z",
                model_tier="cheap",
                token_in=0,
                token_out=0,
                scope=Scope(level=ScopeLevel.org),
                status="success",
            )


# ---------------------------------------------------------------------------
# IdempotencyKey
# ---------------------------------------------------------------------------

class TestIdempotencyKey:
    def test_valid_key(self):
        k = IdempotencyKey(key="evt-hubspot-deal-99-stage-changed-2025-03-01")
        assert k.key.startswith("evt-")

    def test_empty_key_rejected(self):
        with pytest.raises(ValidationError):
            IdempotencyKey(key="")
