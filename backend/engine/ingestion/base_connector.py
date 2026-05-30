from abc import ABC, abstractmethod

from engine.spine.types import BusinessEvent


class BaseConnector(ABC):
    source_system: str

    @abstractmethod
    def pull(self) -> list[BusinessEvent]: ...
