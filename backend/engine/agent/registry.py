from engine.spine.types import AgentSpec, Scope, ScopeLevel


class NoMatchingAgent(Exception):
    pass


class AgentRegistry:
    def __init__(self) -> None:
        self._specs: list[AgentSpec] = []

    def register(self, spec: AgentSpec) -> None:
        self._specs.append(spec)

    def route(self, trigger: str, scope: Scope) -> AgentSpec:
        matches = [
            s for s in self._specs
            if trigger in s.wake_triggers and _scope_compatible(s.scope, scope)
        ]
        if not matches:
            raise NoMatchingAgent(
                f"No agent handles trigger={trigger!r} at scope_level={scope.level}"
            )
        return matches[0]

    def all_specs(self) -> list[AgentSpec]:
        return list(self._specs)


def _scope_compatible(agent_scope: Scope, request_scope: Scope) -> bool:
    if agent_scope.level == ScopeLevel.org:
        return True
    return agent_scope.level == request_scope.level
