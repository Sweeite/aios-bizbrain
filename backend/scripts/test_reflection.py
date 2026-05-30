import sys, os
backend_dir = os.path.join(os.path.dirname(__file__), '..')
repo_root = os.path.join(backend_dir, '..')
sys.path.insert(0, os.path.abspath(backend_dir))
sys.path.insert(0, os.path.abspath(repo_root))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from engine.ingestion.entity_resolver import EntityResolver
from engine.ingestion.memory_writer import MemoryWriter
from engine.worker.tasks.reflection import reflect_on_memory_write
from packs.consulting.connectors.hubspot_mock import HubSpotMockConnector

events = HubSpotMockConnector().pull()
resolver = EntityResolver(known_entities={"client-northpath-001": "client"})
writer = MemoryWriter(on_write=reflect_on_memory_write.delay)

for event in events:
    resolved = resolver.resolve(event)
    writer.write(resolved)
    print("Queued reflection for:", event.id)

print("PASS")
