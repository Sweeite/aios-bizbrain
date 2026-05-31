from datetime import datetime, timezone

from engine.spine.types import ConnectorHealthRecord, ConnectorStatus

KNOWN_SYSTEMS = [
    "hubspot", "gmail", "calendar", "asana",
    "slack", "quickbooks", "harvest", "zoom",
]


class ConnectorHealthService:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorHealthRecord] = {
            s: ConnectorHealthRecord(source_system=s)
            for s in KNOWN_SYSTEMS
        }

    def get_all(self) -> list[ConnectorHealthRecord]:
        return list(self._records.values())

    def get(self, source_system: str) -> ConnectorHealthRecord | None:
        return self._records.get(source_system)

    def record_sync(
        self,
        source_system: str,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        record = self._records.get(source_system)
        if record is None:
            record = ConnectorHealthRecord(source_system=source_system)
            self._records[source_system] = record
        if success:
            self._records[source_system] = ConnectorHealthRecord(
                source_system=source_system,
                status=ConnectorStatus.healthy,
                last_sync_at=datetime.now(tz=timezone.utc),
                error_message=None,
            )
        else:
            self._records[source_system] = ConnectorHealthRecord(
                source_system=source_system,
                status=ConnectorStatus.broken,
                last_sync_at=record.last_sync_at,
                error_message=error_message,
            )

    def reconnect(self, source_system: str) -> ConnectorHealthRecord | None:
        record = self._records.get(source_system)
        if record is None:
            return None
        reset = ConnectorHealthRecord(
            source_system=source_system,
            status=ConnectorStatus.healthy,
            last_sync_at=record.last_sync_at,
            error_message=None,
        )
        self._records[source_system] = reset
        return reset
