from typing import Callable

from engine.spine.types import ToolSpec


class ToolNotFound(Exception):
    pass


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolSpec, Callable]] = {}

    def register(self, spec: ToolSpec, fn: Callable) -> None:
        self._tools[spec.name] = (spec, fn)

    def get(self, name: str) -> tuple[ToolSpec, Callable]:
        if name not in self._tools:
            raise ToolNotFound(f"No tool registered with name={name!r}")
        return self._tools[name]
