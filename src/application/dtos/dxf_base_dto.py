
from abc import ABC
from dataclasses import dataclass

@dataclass
class DXFBaseDTO(ABC):
    id: int
    selected: bool
