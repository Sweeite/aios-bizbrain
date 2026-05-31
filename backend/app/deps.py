from engine.observability.run_store import InMemoryRunStore
from engine.observability.span_store import InMemorySpanStore
from engine.tools.executor import ToolExecutor
from engine.tools.registry import ToolRegistry

_executor: ToolExecutor | None = None
_run_store: InMemoryRunStore | None = None
_span_store: InMemorySpanStore | None = None


def get_executor() -> ToolExecutor:
    global _executor
    if _executor is None:
        _executor = ToolExecutor(ToolRegistry())
    return _executor


def get_run_store() -> InMemoryRunStore:
    global _run_store
    if _run_store is None:
        _run_store = InMemoryRunStore()
    return _run_store


def get_span_store() -> InMemorySpanStore:
    global _span_store
    if _span_store is None:
        _span_store = InMemorySpanStore()
    return _span_store
