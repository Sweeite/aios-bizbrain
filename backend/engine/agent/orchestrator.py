import uuid
from datetime import datetime, timezone

from engine.agent.agents.account import AccountAgent, AgentStepResult
from engine.agent.live import LiveQuery
from engine.agent.registry import AgentRegistry
from engine.agent.span_emitter import SpanEmitter
from engine.ingestion.memory_writer import MemoryWriter
from engine.spine.types import Run, Scope, ScopeLevel, Span, SpanOp

ROUTING_MODEL = "claude-haiku-4-5-20251001"


class Orchestrator:
    def __init__(
        self,
        registry: AgentRegistry,
        memory_writer: MemoryWriter,
        live: LiveQuery,
        anthropic_client,
        span_emitter: SpanEmitter | None = None,
        reflection_task=None,
        tool_executor=None,
        idempotency_key: str | None = None,
        run_store=None,
    ) -> None:
        self._registry = registry
        self._memory = memory_writer
        self._live = live
        self._client = anthropic_client
        self._emitter = span_emitter or SpanEmitter()
        self._reflection_task = reflection_task
        self._tool_executor = tool_executor
        self._idempotency_key = idempotency_key
        self._run_store = run_store

    def handle(
        self,
        trigger: str,
        entity_ref: str,
        parent_scope: Scope | None = None,
    ) -> AgentStepResult:
        run_id = str(uuid.uuid4())
        request_scope = Scope(level=ScopeLevel.entity, entity_ref=entity_ref)

        # Create and persist run record
        run_started = datetime.now(timezone.utc)
        run = Run(
            run_id=run_id,
            initiated_by=trigger,
            scope=request_scope,
            started_at=run_started,
            status="running",
        )
        if self._run_store is not None:
            self._run_store.save(run)

        # Route: capability + scope match (declarative — no hardcoded agent names)
        spec = self._registry.route(trigger, request_scope)

        # Resolve effective scope from spec, then clamp to parent if provided
        resolved = _resolve_scope(spec.scope, entity_ref)
        agent_scope = _bound_scope(resolved, parent_scope)

        # Orchestrator span wraps the whole operation
        orch_span_id = str(uuid.uuid4())
        orch_started = datetime.now(timezone.utc)

        # Recall — scope-filtered episodic memory (emit memory span)
        recall_started = datetime.now(timezone.utc)
        memory_records = self._memory.recall(entity_ref, agent_scope)
        recall_ended = datetime.now(timezone.utc)

        mem_span = Span(
            span_id=str(uuid.uuid4()),
            run_id=run_id,
            parent_span_id=orch_span_id,
            actor="memory-writer",
            op=SpanOp.memory,
            input_ref=f"recall:{entity_ref}",
            output_ref=f"records:{len(memory_records)}",
            started_at=recall_started,
            ended_at=recall_ended,
            model_tier="n/a",
            token_in=0,
            token_out=0,
            scope=agent_scope,
            status="ok",
        )
        self._emitter.emit(mem_span)

        # Live context (always fused — never chosen over recall)
        live_context = self._live.query(entity_ref)

        # Reason + act (fused context reaches agent)
        result = AccountAgent().run(
            entity_ref=entity_ref,
            memory_records=memory_records,
            live_context=live_context,
            scope=agent_scope,
            run_id=run_id,
            anthropic_client=self._client,
            tool_executor=self._tool_executor,
            idempotency_key=self._idempotency_key,
            parent_span_id=orch_span_id,
        )

        self._emitter.emit(result.span)

        # Emit orchestrator span
        orch_span = Span(
            span_id=orch_span_id,
            run_id=run_id,
            parent_span_id=None,
            actor="orchestrator",
            op=SpanOp.reason,
            input_ref=f"trigger:{trigger}:{entity_ref}",
            output_ref=f"agent_result:{entity_ref}",
            started_at=orch_started,
            ended_at=datetime.now(timezone.utc),
            model_tier="n/a",
            token_in=0,
            token_out=0,
            scope=agent_scope,
            status="ok",
        )
        self._emitter.emit(orch_span)

        # Mark run as done
        if self._run_store is not None:
            self._run_store.save(Run(
                run_id=run_id,
                initiated_by=trigger,
                scope=request_scope,
                started_at=run_started,
                ended_at=datetime.now(timezone.utc),
                status="done",
            ))

        if self._reflection_task is not None:
            self._reflection_task.delay(
                run_id=run_id,
                agent_name=spec.name,
                entity_ref=entity_ref,
                draft=result.draft,
            )

        return result


def _resolve_scope(spec_scope: Scope, entity_ref: str) -> Scope:
    """Resolve placeholder entity_ref in AgentSpec scope to the actual entity."""
    if spec_scope.level == ScopeLevel.entity:
        return Scope(level=ScopeLevel.entity, entity_ref=entity_ref)
    return Scope(level=spec_scope.level)


def _bound_scope(agent_scope: Scope, parent_scope: Scope | None) -> Scope:
    """Clamp agent_scope so it never exceeds parent_scope in breadth."""
    if parent_scope is None:
        return agent_scope
    _rank = {
        ScopeLevel.user_private: 0,
        ScopeLevel.entity: 1,
        ScopeLevel.team: 2,
        ScopeLevel.org: 3,
    }
    if _rank[agent_scope.level] > _rank[parent_scope.level]:
        return parent_scope
    return agent_scope
