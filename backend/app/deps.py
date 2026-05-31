from engine.tools.executor import ToolExecutor
from engine.tools.registry import ToolRegistry

_executor: ToolExecutor | None = None


def get_executor() -> ToolExecutor:
    global _executor
    if _executor is None:
        _executor = ToolExecutor(ToolRegistry())
    return _executor
