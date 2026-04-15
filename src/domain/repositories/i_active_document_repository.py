from __future__ import annotations

from abc import abstractmethod
from ...domain.entities import DXFDocument
from ...domain.value_objects import Result
from ...domain.repositories import IRepository

class IActiveDocumentRepository(IRepository[DXFDocument]):
    """Репозиторий для АКТИВНЫХ (открытых) документов в памяти"""
    
    @abstractmethod
    def get_by_filename(self, filename: str) -> Result[DXFDocument | None]:
        """Найти активный документ по имени"""
        pass
    
    @abstractmethod
    def get_all(self) -> Result[list[DXFDocument]]:
        """Все активные документы"""
        pass
    
    @abstractmethod
    def count(self) -> Result[int]:
        """Количество активных документов"""
        pass
