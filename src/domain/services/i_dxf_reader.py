
from abc import ABC, abstractmethod
from ...domain.entities import DXFDocument
from ...domain.value_objects import Result

class IDXFReader(ABC):

    @abstractmethod
    def open(self, filepath: str) -> Result[DXFDocument]:
        pass

    @abstractmethod
    def save_svg_preview(
        self,
        filepath: str,
        output_dir: str,
        filename: str = "",
    ) -> Result[str]:
        pass
