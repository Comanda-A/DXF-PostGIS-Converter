from __future__ import annotations

from abc import abstractmethod
from uuid import UUID
from ...domain.value_objects import Result
from ...domain.entities import DXFContent
from ...domain.repositories import IRepository

class IContentRepository(IRepository[DXFContent]):
    """Репозиторий для содержимого файлов"""

    @abstractmethod
    def get_by_document_id(self, document_id: UUID) -> Result[DXFContent | None]:
        pass
