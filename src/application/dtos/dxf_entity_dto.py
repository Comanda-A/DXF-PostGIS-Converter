
from dataclasses import dataclass
from typing import Any, Dict
from ...application.dtos import DXFBaseDTO

@dataclass
class DXFEntityDTO(DXFBaseDTO):
    name: str
    typename: str
    attributes: Dict[str, Any]
    geometries: Dict[str, Any]
