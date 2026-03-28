
from uuid import UUID
from ...application.events import IEvent
from ...application.dtos import DXFDocumentDTO
from ...application.events import IAppEvents
from ...infrastructure.qgis import QtEvent 


class QtAppEvents(IAppEvents):
    
    def __init__(self):
        super().__init__()
        
        # Инициализация событий
        self._on_document_opened = QtEvent[list[DXFDocumentDTO]]()
        self._on_document_saved = QtEvent[list[DXFDocumentDTO]]()
        self._on_document_closed = QtEvent[list[UUID]]()
        self._on_document_modified = QtEvent[list[DXFDocumentDTO]]()
        self._on_language_changed = QtEvent[str]()

    @property
    def on_document_opened(self) -> IEvent[list[DXFDocumentDTO]]:
        """Событие открытия документа"""
        return self._on_document_opened

    @property
    def on_document_saved(self) -> IEvent[list[DXFDocumentDTO]]:
        """Событие сохранения документа"""
        return self._on_document_saved

    @property
    def on_document_closed(self) -> IEvent[list[UUID]]:
        """Событие закрытия документа"""
        return self._on_document_closed

    @property
    def on_document_modified(self) -> IEvent[list[DXFDocumentDTO]]:
        """Событие модификации документа"""
        return self._on_document_modified

    @property
    def on_language_changed(self) -> IEvent[str]:
        """Событие изменения языка"""
        return self._on_language_changed
