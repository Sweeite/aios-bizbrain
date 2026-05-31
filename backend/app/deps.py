from engine.clients.profile_service import ClientProfileService
from engine.connectors.health_service import ConnectorHealthService
from engine.ingestion.entity_resolver import EntityResolver
from engine.ingestion.memory_writer import MemoryWriter
from engine.observability.run_store import InMemoryRunStore
from engine.observability.span_store import InMemorySpanStore
from engine.tools.executor import ToolExecutor
from engine.tools.registry import ToolRegistry

_executor: ToolExecutor | None = None
_run_store: InMemoryRunStore | None = None
_span_store: InMemorySpanStore | None = None
_client_profile_service: ClientProfileService | None = None
_connector_health_service: ConnectorHealthService | None = None


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


def get_connector_health_service() -> ConnectorHealthService:
    global _connector_health_service
    if _connector_health_service is None:
        _connector_health_service = ConnectorHealthService()
    return _connector_health_service


def get_client_profile_service() -> ClientProfileService:
    global _client_profile_service
    if _client_profile_service is None:
        from packs.consulting.clients import CLIENTS, KNOWN_CLIENT_IDS
        from packs.consulting.connectors.registry import ConnectorRegistry

        events = ConnectorRegistry().pull_all()
        resolver = EntityResolver({cid: cid for cid in KNOWN_CLIENT_IDS})
        writer = MemoryWriter()
        for event in events:
            resolved = resolver.resolve(event)
            writer.write(resolved)
        _client_profile_service = ClientProfileService(CLIENTS, writer, events)
    return _client_profile_service
