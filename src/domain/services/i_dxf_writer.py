
from abc import ABC, abstractmethod
from typing import Sequence
from ...domain.entities import DXFDocument
from ...domain.entities import DXFEntity
from ...domain.value_objects import Result, Unit

class IDXFWriter(ABC):

    @abstractmethod
    def save(self, document: DXFDocument, filepath: str) -> Result[Unit]:
        pass

    @abstractmethod
    def save_selected_by_handles(
        self,
        source_filepath: str,
        output_path: str,
        selected_handles: set[str],
    ) -> Result[int]:
        """Сохраняет только сущности с handle из selected_handles.

        Возвращает количество удаленных сущностей.
        """
        pass

    @abstractmethod
    def reconstruct_from_entities(self, entities: Sequence[DXFEntity]) -> Result[tuple[bytes, str]]:
        """Собирает DXF из сущностей, созданных из таблиц, и возвращает bytes + детальный отчет."""
        pass
