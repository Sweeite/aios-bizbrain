"""
Slice 11 prove script — full mock connector set.
Run from backend/: python scripts/prove_slice11.py
"""
import sys
from pathlib import Path

# backend/ is cwd; packs/ lives one level up at the repo root
sys.path.insert(0, str(Path(__file__).parent.parent))          # backend/
sys.path.insert(0, str(Path(__file__).parent.parent.parent))   # repo root

from packs.consulting.connectors.registry import ConnectorRegistry

registry = ConnectorRegistry()
connectors = registry.all()
events = registry.pull_all()

source_systems = sorted({e.source_system for e in events})
print(f"{len(events)} events from {len(connectors)} connectors: {', '.join(source_systems)}")
print()

for system in source_systems:
    system_events = [e for e in events if e.source_system == system]
    print(f"  {system} ({len(system_events)} event{'s' if len(system_events) != 1 else ''}):")
    for e in system_events:
        print(f"    [{e.event_type}] {e.id}")
