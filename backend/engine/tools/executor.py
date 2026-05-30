from engine.spine.types import AutonomyTier, ParkedApprovalRequest, Scope, ScopeLevel
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
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
        self._parked: dict[str, ParkedApprovalRequest] = {}

    def execute(
        self,
        tool_name: str,
        inputs: dict,
        scope: Scope,
        requesting_agent: str,
        principal: str,
        rationale: str,
        idempotency_key: str,
    ) -> str | ParkedApprovalRequest:
        spec, fn = self._registry.get(tool_name)

        if _SCOPE_RANK[scope.level] < _SCOPE_RANK[spec.scope_required]:
            raise InsufficientScope(
                f"Tool {tool_name!r} requires scope>={spec.scope_required}, "
                f"got {scope.level}"
            )

        if spec.tier in _IMMEDIATE_TIERS:
            return fn(inputs, dry_run=False)

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
        return request
