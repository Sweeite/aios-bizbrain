-- AIOS BizBrain — spine schema
-- Applies cleanly via: supabase db push
-- All tables use UUIDs. pgvector extension required for vector stores.

-- ── Extensions ───────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ── Entity memory ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entity_memory (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_ref      TEXT NOT NULL,
    entity_type     TEXT NOT NULL CHECK (entity_type IN ('client','contact','employee','engagement')),
    payload         JSONB NOT NULL DEFAULT '{}',
    provenance      TEXT NOT NULL,
    as_of           TIMESTAMPTZ NOT NULL,
    lifespan_days   INTEGER,
    scope_level     TEXT NOT NULL,
    scope_entity_ref TEXT,
    scope_team_ref  TEXT,
    scope_user_ref  TEXT,
    confidence      TEXT NOT NULL CHECK (confidence IN ('observed','inferred','stated_once')),
    superseded_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS entity_memory_entity_ref_idx ON entity_memory (entity_ref);
CREATE INDEX IF NOT EXISTS entity_memory_scope_idx ON entity_memory (scope_level, scope_entity_ref);

-- ── Semantic memory ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS semantic_memory (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic           TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}',
    embedding       vector(1536),
    provenance      TEXT NOT NULL,
    as_of           TIMESTAMPTZ NOT NULL,
    lifespan_days   INTEGER,
    scope_level     TEXT NOT NULL DEFAULT 'org',
    confidence      TEXT NOT NULL CHECK (confidence IN ('observed','inferred','stated_once')),
    superseded_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS semantic_memory_topic_idx ON semantic_memory (topic);

-- ── Episodic memory ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS episodic_memory (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_event_id TEXT NOT NULL,
    source_system   TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}',
    embedding       vector(1536),
    provenance      TEXT NOT NULL,
    as_of           TIMESTAMPTZ NOT NULL,
    lifespan_days   INTEGER DEFAULT 365,
    scope_level     TEXT NOT NULL,
    scope_entity_ref TEXT,
    scope_team_ref  TEXT,
    scope_user_ref  TEXT,
    confidence      TEXT NOT NULL CHECK (confidence IN ('observed','inferred','stated_once')),
    consolidated_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_event_id, source_system)
);
CREATE INDEX IF NOT EXISTS episodic_memory_entity_ref_idx ON episodic_memory (scope_entity_ref);
CREATE INDEX IF NOT EXISTS episodic_memory_as_of_idx ON episodic_memory (as_of DESC);
CREATE INDEX IF NOT EXISTS episodic_memory_event_type_idx ON episodic_memory (event_type);

-- ── Procedural memory ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS procedural_memory (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    steps           JSONB NOT NULL DEFAULT '[]',
    payload         JSONB NOT NULL DEFAULT '{}',
    provenance      TEXT NOT NULL,
    as_of           TIMESTAMPTZ NOT NULL,
    lifespan_days   INTEGER,
    scope_level     TEXT NOT NULL DEFAULT 'org',
    confidence      TEXT NOT NULL CHECK (confidence IN ('observed','inferred','stated_once')),
    superseded_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Durable intake queue ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS intake_queue (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    idempotency_key TEXT NOT NULL UNIQUE,
    source_system   TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','done','failed')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    enqueued_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS intake_queue_status_idx ON intake_queue (status, enqueued_at);

-- ── Tool registry ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tool_registry (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL UNIQUE,
    system          TEXT NOT NULL,
    mode            TEXT NOT NULL CHECK (mode IN ('read','write')),
    tier            TEXT NOT NULL CHECK (tier IN ('T0','T1','T2','T3','T4')),
    inputs_schema   JSONB NOT NULL DEFAULT '{}',
    scope_required  TEXT NOT NULL,
    reversible      BOOLEAN NOT NULL DEFAULT TRUE,
    undo_tool       TEXT,
    side_effects    JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Agent registry ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_registry (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL UNIQUE,
    role            TEXT NOT NULL,
    scope_level     TEXT NOT NULL,
    scope_entity_ref TEXT,
    scope_team_ref  TEXT,
    scope_user_ref  TEXT,
    toolset         JSONB NOT NULL DEFAULT '[]',
    model_tier      JSONB NOT NULL DEFAULT '{}',
    wake_triggers   JSONB NOT NULL DEFAULT '[]',
    playbooks       JSONB NOT NULL DEFAULT '[]',
    spawn_policy    JSONB NOT NULL DEFAULT '{}',
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Autonomy config (per-client tier overrides) ──────────────────────────────
CREATE TABLE IF NOT EXISTS autonomy_config (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tool_name       TEXT NOT NULL UNIQUE REFERENCES tool_registry (name),
    tier_override   TEXT NOT NULL CHECK (tier_override IN ('T0','T1','T2','T3','T4')),
    reason          TEXT,
    set_by          TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Approval queue (durable, never silently expires) ─────────────────────────
CREATE TABLE IF NOT EXISTS approval_queue (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    idempotency_key     TEXT NOT NULL UNIQUE,
    action              TEXT NOT NULL,
    preview             TEXT NOT NULL,
    requesting_agent    TEXT NOT NULL,
    principal           TEXT NOT NULL,
    scope_level         TEXT NOT NULL,
    scope_entity_ref    TEXT,
    rationale           TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','expired')),
    reviewed_by         TEXT,
    review_note         TEXT,
    parked_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at         TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS approval_queue_status_idx ON approval_queue (status, parked_at);
CREATE INDEX IF NOT EXISTS approval_queue_principal_idx ON approval_queue (principal, status);

-- ── Audit log (immutable, append-only) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action          TEXT NOT NULL,
    tool_name       TEXT,
    tier            TEXT,
    agent           TEXT NOT NULL,
    principal       TEXT NOT NULL,
    scope_level     TEXT NOT NULL,
    scope_entity_ref TEXT,
    approval_ref    UUID,
    idempotency_key TEXT NOT NULL,
    outcome         TEXT NOT NULL,
    payload_ref     TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Audit log is append-only; no UPDATE/DELETE permissions should be granted.
CREATE INDEX IF NOT EXISTS audit_log_principal_idx ON audit_log (principal, occurred_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_agent_idx ON audit_log (agent, occurred_at DESC);

-- ── Telemetry — runs ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    initiated_by    TEXT NOT NULL,
    scope_level     TEXT NOT NULL,
    scope_entity_ref TEXT,
    started_at      TIMESTAMPTZ NOT NULL,
    ended_at        TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running'
);
CREATE INDEX IF NOT EXISTS runs_initiated_by_idx ON runs (initiated_by, started_at DESC);

-- ── Telemetry — spans ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS spans (
    span_id         TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs (run_id),
    parent_span_id  TEXT,
    actor           TEXT NOT NULL,
    op              TEXT NOT NULL CHECK (op IN ('tool','memory','reason')),
    input_ref       TEXT,
    output_ref      TEXT,
    started_at      TIMESTAMPTZ NOT NULL,
    ended_at        TIMESTAMPTZ,
    model_tier      TEXT,
    token_in        INTEGER NOT NULL DEFAULT 0,
    token_out       INTEGER NOT NULL DEFAULT 0,
    scope_level     TEXT NOT NULL,
    scope_entity_ref TEXT,
    status          TEXT NOT NULL,
    outcome         TEXT
);
CREATE INDEX IF NOT EXISTS spans_run_id_idx ON spans (run_id);
CREATE INDEX IF NOT EXISTS spans_actor_idx ON spans (actor, started_at DESC);
