
from abc import ABC, abstractmethod
from ...domain.entities import DXFDocument
from ...domain.value_objects import Result

class IDXFReader(ABC):

    @abstractmethod
    def open(self, filepath: str) -> Result[DXFDocument]:
        pass
