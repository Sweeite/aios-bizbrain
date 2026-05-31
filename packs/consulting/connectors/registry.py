from engine.ingestion.base_connector import BaseConnector
from engine.spine.types import BusinessEvent

from packs.consulting.connectors.asana_mock import AsanaMockConnector
from packs.consulting.connectors.calendar_mock import CalendarMockConnector
from packs.consulting.connectors.gmail_mock import GmailMockConnector
from packs.consulting.connectors.harvest_mock import HarvestMockConnector
from packs.consulting.connectors.hubspot_mock import HubSpotMockConnector
from packs.consulting.connectors.quickbooks_mock import QuickBooksMockConnector
from packs.consulting.connectors.slack_mock import SlackMockConnector
from packs.consulting.connectors.zoom_mock import ZoomMockConnector

_DEFAULT_CONNECTORS: list[BaseConnector] = [
    HubSpotMockConnector(),
    GmailMockConnector(),
    CalendarMockConnector(),
    AsanaMockConnector(),
    SlackMockConnector(),
    QuickBooksMockConnector(),
    HarvestMockConnector(),
    ZoomMockConnector(),
]


class ConnectorRegistry:
    def __init__(self, extra_connectors: list[BaseConnector] | None = None) -> None:
        self._connectors: list[BaseConnector] = list(_DEFAULT_CONNECTORS)
        if extra_connectors:
            self._connectors.extend(extra_connectors)

    def all(self) -> list[BaseConnector]:
        return list(self._connectors)

    def pull_all(self) -> list[BusinessEvent]:
        seen: set[str] = set()
        result: list[BusinessEvent] = []
        for connector in self._connectors:
            for event in connector.pull():
                if event.id not in seen:
                    seen.add(event.id)
                    result.append(event)
        return result
