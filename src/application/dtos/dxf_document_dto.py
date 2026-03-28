
from dataclasses import dataclass
from typing import List
from ...application.dtos import DXFBaseDTO, DXFLayerDTO


@dataclass
class DXFDocumentDTO(DXFBaseDTO):
    filename: str
    filepath: str
    layers: List[DXFLayerDTO]
