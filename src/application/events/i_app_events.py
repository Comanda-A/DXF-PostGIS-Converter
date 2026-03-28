
from uuid import UUID
from ...application.events import IEvent
from ...application.dtos import DXFDocumentDTO
from abc import ABC, abstractmethod

class IAppEvents(ABC):
    
    @property
    @abstractmethod
    def on_document_opened(self) -> IEvent[list[DXFDocumentDTO]]:
        pass

    @property
    @abstractmethod
    def on_document_saved(self) -> IEvent[list[DXFDocumentDTO]]:
        pass

    @property
    @abstractmethod
    def on_document_closed(self) -> IEvent[list[UUID]]:
        pass

    @property
    @abstractmethod
    def on_document_modified(self) -> IEvent[list[DXFDocumentDTO]]:
        pass

    @property
    @abstractmethod
    def on_language_changed(self) -> IEvent[str]:
        pass
