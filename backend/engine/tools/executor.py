import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from engine.spine.types import AuditRecord, AutonomyTier, ParkedApprovalRequest, Scope, ScopeLevel, Span, SpanOp
from engine.tools.registry import ToolRegistry

_SCOPE_RANK = {
    ScopeLevel.user_private: 0,
    ScopeLevel.entity: 1,
    ScopeLevel.team: 2,
    ScopeLevel.org: 3,
}

_IMMEDIATE_TIERS = {AutonomyTier.T0, AutonomyTier.T1}


class InsufficientScope(Exception):
    pass


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        on_park: Callable[[ParkedApprovalRequest], None] | None = None,
        span_emitter=None,
        audit_store=None,
        notification_router=None,
    ) -> None:
        self._registry = registry
        self._parked: dict[str, ParkedApprovalRequest] = {}
        self._parked_meta: dict[str, dict] = {}
        self._resolved: set[str] = set()
        self._resolved_results: dict[str, str] = {}
        self._on_park = on_park
        self._emitter = span_emitter
        self._audit_store = audit_store
        self._notification_router = notification_router

    def list_pending(self) -> list[ParkedApprovalRequest]:
        return list(self._parked.values())

    def approve(
        self,
        idempotency_key: str,
        override_body: str | None = None,
        approver: str | None = None,
    ) -> str:
        if idempotency_key in self._resolved:
            return self._resolved_results.get(idempotency_key, "")
        if idempotency_key not in self._parked_meta:
            raise KeyError(idempotency_key)

        meta = self._parked_meta[idempotency_key]
        fn = meta["fn"]
        inputs = dict(meta["inputs"])
        original_preview = self._parked[idempotency_key].preview

        if override_body is not None:
            inputs = {**inputs, "body": override_body}

        started_at = meta["started_at"]
        ended_at = datetime.now(timezone.utc)
        result = fn(inputs, dry_run=False)

        # Eval label: positive for straight approve, soft_negative for edit
        if override_body is not None:
            eval_label = "soft_negative"
            eval_note = f"original: {original_preview!r} → edited: {override_body!r}"
        else:
            eval_label = "positive"
            eval_note = None

        if self._emitter is not None:
            span = Span(
                span_id=str(uuid.uuid4()),
                run_id=meta.get("run_id") or "",
                parent_span_id=meta.get("parent_span_id"),
                actor="tool-executor",
                op=SpanOp.tool,
                input_ref=f"tool:{meta['tool_name']}:{idempotency_key}",
                output_ref=f"result:{idempotency_key}",
                started_at=started_at,
                ended_at=ended_at,
                model_tier="n/a",
                token_in=0,
                token_out=0,
                scope=meta["scope"],
                status="ok",
                eval_label=eval_label,
                eval_note=eval_note,
            )
            self._emitter.emit(span)

        if self._audit_store is not None:
            after_state = override_body if override_body is not None else result
            record = AuditRecord(
                id=str(uuid.uuid4()),
                action=meta["tool_name"],
                tool_name=meta["tool_name"],
                tier=meta.get("tier"),
                agent=meta["requesting_agent"],
                principal=meta["principal"],
                scope_level=meta["scope"].level.value,
                scope_entity_ref=meta["scope"].entity_ref,
                idempotency_key=idempotency_key,
                outcome="approved",
                occurred_at=ended_at,
                approver=approver,
                before_state=original_preview,
                after_state=str(after_state),
            )
            self._audit_store.save(record)

        del self._parked[idempotency_key]
        del self._parked_meta[idempotency_key]
        self._resolved.add(idempotency_key)
        self._resolved_results[idempotency_key] = result
        return result

    def reject(
        self,
        idempotency_key: str,
        reason: str,
        approver: str | None = None,
    ) -> None:
        if idempotency_key in self._resolved:
            return
        if idempotency_key not in self._parked:
            raise KeyError(idempotency_key)

        meta = self._parked_meta[idempotency_key]
        ended_at = datetime.now(timezone.utc)

        if self._emitter is not None:
            span = Span(
                span_id=str(uuid.uuid4()),
                run_id=meta.get("run_id") or "",
                parent_span_id=meta.get("parent_span_id"),
                actor="tool-executor",
                op=SpanOp.tool,
                input_ref=f"tool:{meta['tool_name']}:{idempotency_key}",
                output_ref=f"rejected:{idempotency_key}",
                started_at=meta["started_at"],
                ended_at=ended_at,
                model_tier="n/a",
                token_in=0,
                token_out=0,
                scope=meta["scope"],
                status="rejected",
                eval_label="negative",
                eval_note=reason,
            )
            self._emitter.emit(span)

        if self._audit_store is not None:
            record = AuditRecord(
                id=str(uuid.uuid4()),
                action=meta["tool_name"],
                tool_name=meta["tool_name"],
                tier=meta.get("tier"),
                agent=meta["requesting_agent"],
                principal=meta["principal"],
                scope_level=meta["scope"].level.value,
                scope_entity_ref=meta["scope"].entity_ref,
                idempotency_key=idempotency_key,
                outcome="rejected",
                occurred_at=ended_at,
                approver=approver,
                before_state=self._parked[idempotency_key].preview,
                after_state=None,
            )
            self._audit_store.save(record)

        del self._parked[idempotency_key]
        del self._parked_meta[idempotency_key]
        self._resolved.add(idempotency_key)

    def execute(
        self,
        tool_name: str,
        inputs: dict,
        scope: Scope,
        requesting_agent: str,
        principal: str,
        rationale: str,
        idempotency_key: str,
        run_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> str | ParkedApprovalRequest:
        spec, fn = self._registry.get(tool_name)

        if _SCOPE_RANK[scope.level] < _SCOPE_RANK[spec.scope_required]:
            raise InsufficientScope(
                f"Tool {tool_name!r} requires scope>={spec.scope_required}, "
                f"got {scope.level}"
            )

        if spec.tier in _IMMEDIATE_TIERS:
            return fn(inputs, dry_run=False)

        if spec.tier == AutonomyTier.T4:
            # Prepare-only: system never executes, human runs the artifact
            return fn(inputs, dry_run=True)

        # T3: park — idempotency check first
        if idempotency_key in self._parked:
            return self._parked[idempotency_key]

        preview = fn(inputs, dry_run=True)
        request = ParkedApprovalRequest(
            action=tool_name,
            preview=preview,
            requesting_agent=requesting_agent,
            principal=principal,
            scope=scope,
            rationale=rationale,
            idempotency_key=idempotency_key,
        )
        self._parked[idempotency_key] = request
        self._parked_meta[idempotency_key] = {
            "fn": fn,
            "inputs": dict(inputs),
            "tool_name": tool_name,
            "tier": spec.tier.value,
            "scope": scope,
            "requesting_agent": requesting_agent,
            "principal": principal,
            "run_id": run_id,
            "parent_span_id": parent_span_id,
            "started_at": datetime.now(timezone.utc),
        }
        if self._on_park is not None:
            self._on_park(request)
        if self._notification_router is not None:
            self._notification_router.route(request)
        return request
