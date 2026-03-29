from __future__ import annotations

from uuid import UUID
from ...domain.repositories import IActiveDocumentRepository
from ...domain.entities import DXFBase, DXFDocument
from ...application.interfaces import ILogger
from ...application.dtos import DXFBaseDTO, DXFDocumentDTO
from ...application.mappers import DXFMapper

class ActiveDocumentService:
    """Сервис для работы с открытыми документами и их объектами"""
    
    def __init__(self, active_repo: IActiveDocumentRepository, logger: ILogger):
        self._active_repo = active_repo
        self._logger = logger
    
    @property
    def _documents(self) -> list[DXFDocument]:
        result =  self._active_repo.get_all()
        if result.is_success:
            return result.value
        return []

    def get_documents_count(self) -> int:
        return len(self._documents)
    
    def get_all(self) -> list[DXFDocumentDTO]:
        return DXFMapper.to_dto(self._documents)
    
    def get_document_by_filename(self, filename: str) -> DXFDocumentDTO | None:
        for doc in self._documents:
            if doc.filename == filename:
                return DXFMapper.to_dto(doc)
        return None
    
    def _get_by_id(self, id: UUID) -> DXFBase | None:
        
        result = self._active_repo.get_all()

        if result.is_success:

            for document in result.value:
                if document.id == id:
                    return document

                if document.content.id == id:
                    return document.content

                if id in document.layers:
                    return document.layers[id]

                for layer in document.layers.values():
                    if id in layer.entities:
                        return layer.entities[id]
        
        else:
            self._logger.error(f"Failed to get all active documents: {result.error}")
            return None
        
    def get_by_id(self, id: UUID) -> DXFBaseDTO | None:
        entity = self._get_by_id(id)
        return DXFMapper.to_dto(entity) if entity else None
    
   