import os, sys
sys.path.insert(0, '..')
from dotenv import load_dotenv
load_dotenv()

import anthropic
from supabase import create_client
from engine.agent.registry import AgentRegistry
from engine.agent.live import LiveQuery
from engine.agent.span_emitter import SpanEmitter
from engine.agent.orchestrator import Orchestrator
from engine.ingestion.entity_resolver import EntityResolver
from engine.ingestion.memory_writer import MemoryWriter
from engine.spine.types import ParkedApprovalRequest
from engine.tools.registry import ToolRegistry
from engine.tools.executor import ToolExecutor
from engine.tools.implementations.draft_email import DraftEmailTool, SPEC as EMAIL_SPEC
from packs.consulting.agent_specs.roster import CONSULTING_AGENTS
from packs.consulting.connectors.hubspot_mock import HubSpotMockConnector

db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])

def park_to_supabase(req: ParkedApprovalRequest) -> None:
    db.table("approval_queue").upsert({
        "idempotency_key":   req.idempotency_key,
        "action":            req.action,
        "preview":           req.preview,
        "requesting_agent":  req.requesting_agent,
        "principal":         req.principal,
        "scope_level":       req.scope.level.value,
        "scope_entity_ref":  req.scope.entity_ref,
        "rationale":         req.rationale,
        "status":            "pending",
    }, on_conflict="idempotency_key").execute()
    print(f"Parked: action={req.action!r}  key={req.idempotency_key!r}")

tool_registry = ToolRegistry()
tool_registry.register(EMAIL_SPEC, DraftEmailTool().execute)
executor = ToolExecutor(tool_registry, on_park=park_to_supabase)

events = HubSpotMockConnector().pull()
resolver = EntityResolver(known_entities={"client-northpath-001": "client"})
writer = MemoryWriter()
for event in events:
    writer.write(resolver.resolve(event))

agent_registry = AgentRegistry()
for spec in CONSULTING_AGENTS:
    agent_registry.register(spec)

emitter = SpanEmitter()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
orch = Orchestrator(
    registry=agent_registry,
    memory_writer=writer,
    live=LiveQuery(),
    anthropic_client=client,
    span_emitter=emitter,
    tool_executor=executor,
    idempotency_key="slice5-proving-path-001",
)
result = orch.handle("deal.stage_changed", "client-northpath-001")

print()
print("=== Draft nudge ===")
print(result.draft)
print()
if result.parked:
    print(f"=== Parked as T3 ===  key={result.parked.idempotency_key!r}")
else:
    print("(No commitment detected — sent as autonomous T1)")
print("PASS — check Supabase Table Editor -> approval_queue")
