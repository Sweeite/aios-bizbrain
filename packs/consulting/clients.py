CLIENTS = [
    {"id": "client-northpath-001", "name": "Northpath"},
    {"id": "client-meridian-001", "name": "Meridian Capital"},
    {"id": "client-vertex-002", "name": "Vertex Partners"},
]

KNOWN_CLIENT_IDS: frozenset[str] = frozenset(c["id"] for c in CLIENTS)
