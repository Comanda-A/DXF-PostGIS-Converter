from __future__ import annotations

from abc import abstractmethod
from ...domain.value_objects import Result
from ...domain.entities import DXFDocument
from ...domain.repositories import IRepository

class IDocumentRepository(IRepository[DXFDocument]):
    """Репозиторий для документов"""

    @abstractmethod
    def get_by_filename(self, filename: str) -> Result[DXFDocument | None]:
        """Найти по имени"""
        pass
    
    @abstractmethod
    def get_all(self) -> Result[list[DXFDocument]]:
        """Все сохраненные документы"""
        pass

    @abstractmethod
    def count(self) -> Result[int]:
        """Количество документов"""
        pass

    @abstractmethod
    def exists(self, filename: str) -> Result[bool]:
        """Проверить существование документа по имени"""
        pass
