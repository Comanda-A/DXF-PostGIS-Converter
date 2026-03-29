from __future__ import annotations

from abc import abstractmethod
from uuid import UUID
from ...domain.value_objects import Result
from ...domain.entities import DXFLayer
from ...domain.repositories import IRepository


class ILayerRepository(IRepository[DXFLayer]):
    """Репозиторий для слоев"""

    @abstractmethod
    def get_by_document_id_and_layer_name(self, document_id: UUID, layer_name: str) -> Result[DXFLayer | None]:
        """Получить по док id и имя слоя"""
        pass

    @abstractmethod
    def get_all_by_document_id(self, document_id: UUID) -> Result[list[DXFLayer]]:
        """Все сохраненные слои для документа"""
        pass

    @abstractmethod
    def get_all(self) -> Result[list[DXFLayer]]:
        """Все сохраненные слои"""
        pass
