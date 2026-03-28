
from dataclasses import dataclass
from typing import List
from ...application.dtos import DXFBaseDTO, DXFEntityDTO

@dataclass
class DXFLayerDTO(DXFBaseDTO):
    name: str
    entities: List[DXFEntityDTO]
