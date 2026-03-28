
from abc import ABC, abstractmethod
from ...domain.entities import DXFDocument
from ...domain.value_objects import Result, Unit

class IDXFWriter(ABC):

    @abstractmethod
    def save(self, document: DXFDocument, filepath: str) -> Result[Unit]:
        pass
