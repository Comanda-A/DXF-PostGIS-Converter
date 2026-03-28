
from uuid import UUID
from typing import List, Optional
from ...domain.entities import DXFDocument
from ...domain.value_objects import Result, Unit
from ...domain.repositories import IActiveDocumentRepository

class ActiveDocumentRepository(IActiveDocumentRepository):
    """Репозиторий для активных (открытых) документов в памяти"""

    def __init__(self):
        self._documents: List[DXFDocument] = []

    def create(self, entity: DXFDocument) -> Result[DXFDocument]:
        self._documents.append(entity)
        return Result.success(entity)
    
    def update(self, entity: DXFDocument) -> Result[DXFDocument]:
        for idx, doc in enumerate(self._documents):
            if doc.id == entity.id:
                self._documents[idx] = entity
                return Result.success(entity)
        return Result.fail(f"Document with id {entity.id} not found")
    
    def remove(self, id: UUID) -> Result[Unit]:
        for idx, doc in enumerate(self._documents):
            if doc.id == id:
                del self._documents[idx]
                return Result.success(Unit())
        return Result.fail(f"Document with id {id} not found")
    
    def get_by_id(self, id: UUID) -> Result[Optional[DXFDocument]]:
        for doc in self._documents:
            if doc.id == id:
                return Result.success(doc)
        return Result.fail(f"Document with id {id} not found")

    def get_by_filename(self, filename: str) -> Result[Optional[DXFDocument]]:
        for doc in self._documents:
            if doc.filename == filename:
                return Result.success(doc)
        return Result.fail(f"Document with filename {filename} not found")
    
    def get_all(self) -> Result[List[DXFDocument]]:
        return Result.success(self._documents.copy())
    
    def count(self) -> Result[int]:
        return Result.success(len(self._documents))