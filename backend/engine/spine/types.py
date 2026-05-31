"""
Shared spine types — defined once, referenced everywhere.
Engine has zero pack/client-specific references.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, field_validator, model_validator


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------

class ScopeLevel(str, Enum):
    org = "org"
    team = "team"
    entity = "entity"
    user_private = "user_private"


class Scope(BaseModel):
    level: ScopeLevel
    entity_ref: str | None = None
    team_ref: str | None = None
    user_ref: str | None = None

    @model_validator(mode="after")
    def _refs_match_level(self) -> "Scope":
        if self.level == ScopeLevel.entity and not self.entity_ref:
            raise ValueError("entity_ref required when level=entity")
        if self.level == ScopeLevel.user_private and not self.user_ref:
            raise ValueError("user_ref required when level=user_private")
        return self


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

class EntityType(str, Enum):
    client = "client"
    contact = "contact"
    employee = "employee"
    engagement = "engagement"


class Entity(BaseModel):
    id: str
    type: EntityType
    name: str
    # identity fields that also exist in source systems carry as_of dates
    title: str | None = None
    title_as_of: datetime | None = None
    synthesis: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# BusinessEvent  (ingestion envelope)
# ---------------------------------------------------------------------------

class BusinessEvent(BaseModel):
    id: str
    source_system: str
    event_type: str
    timestamp: datetime
    actor: str
    entities: list[str] = []
    raw_ref: str
    body: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# MemoryRecord
# ---------------------------------------------------------------------------

class MemoryStore(str, Enum):
    entity = "entity"
    semantic = "semantic"
    episodic = "episodic"
    procedural = "procedural"


class Confidence(str, Enum):
    observed = "observed"
    inferred = "inferred"
    stated_once = "stated_once"


class MemoryRecord(BaseModel):
    store: MemoryStore
    payload: dict[str, Any]
    provenance: str
    temporal_validity: dict[str, Any]  # {as_of, lifespan_days}
    scope: Scope
    confidence: Confidence


# ---------------------------------------------------------------------------
# AutonomyTier
# ---------------------------------------------------------------------------

class AutonomyTier(str, Enum):
    T0 = "T0"   # read-only
    T1 = "T1"   # safe write
    T2 = "T2"   # notify after
    T3 = "T3"   # approve first
    T4 = "T4"   # prepare only — human executes


# ---------------------------------------------------------------------------
# ToolSpec
# ---------------------------------------------------------------------------

class ToolMode(str, Enum):
    read = "read"
    write = "write"


class ToolSpec(BaseModel):
    name: str
    inputs: dict[str, Any]
    system: str
    mode: ToolMode
    tier: AutonomyTier
    scope_required: ScopeLevel
    reversible: bool
    undo: str | None = None
    side_effects: list[str] = []


# ---------------------------------------------------------------------------
# ParkedApprovalRequest
# ---------------------------------------------------------------------------

class ParkedApprovalRequest(BaseModel):
    action: str
    preview: str
    requesting_agent: str
    principal: str
    scope: Scope
    rationale: str
    idempotency_key: str


# ---------------------------------------------------------------------------
# AgentSpec
# ---------------------------------------------------------------------------

class AgentSpec(BaseModel):
    name: str
    role: str
    scope: Scope
    toolset: list[str]
    model_tier: dict[str, str]
    wake_triggers: list[str]
    playbooks: list[str]
    spawn_policy: dict[str, Any]


# ---------------------------------------------------------------------------
# Run / Span  (observability)
# ---------------------------------------------------------------------------

class SpanOp(str, Enum):
    tool = "tool"
    memory = "memory"
    reason = "reason"


class Run(BaseModel):
    run_id: str
    initiated_by: str
    scope: Scope
    started_at: datetime
    ended_at: datetime | None = None
    status: str = "running"


class Span(BaseModel):
    span_id: str
    run_id: str
    parent_span_id: str | None = None
    actor: str
    op: SpanOp
    input_ref: str
    output_ref: str
    started_at: datetime
    ended_at: datetime | None = None
    model_tier: str
    token_in: int
    token_out: int
    scope: Scope
    status: str
    outcome: str | None = None
    eval_label: str | None = None
    eval_note: str | None = None


# ---------------------------------------------------------------------------
# AuditRecord
# ---------------------------------------------------------------------------

class AuditRecord(BaseModel):
    id: str
    action: str
    tool_name: str | None = None
    tier: str | None = None
    agent: str
    principal: str
    scope_level: str
    scope_entity_ref: str | None = None
    approval_ref: str | None = None
    idempotency_key: str
    outcome: str
    payload_ref: str | None = None
    occurred_at: datetime
    approver: str | None = None
    before_state: str | None = None
    after_state: str | None = None


# ---------------------------------------------------------------------------
# IdempotencyKey
# ---------------------------------------------------------------------------

class IdempotencyKey(BaseModel):
    key: str

    @field_validator("key")
    @classmethod
    def _not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("idempotency key must not be empty")
        return v
