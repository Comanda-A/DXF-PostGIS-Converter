
from abc import ABC
from uuid import uuid4, UUID
from typing import Optional

class DXFBase(ABC):
    
    def __init__(self, id: Optional[UUID] = None, selected: bool = True):
        self._id = id or uuid4()
        self._selected = selected

    @property
    def id(self) -> UUID:
        """Уникальный идентификатор объекта"""
        return self._id

    @property
    def is_selected(self) -> bool:
        """Флаг выделения объекта"""
        return self._selected
    
    def set_selected(self, value: bool):
        self._selected = value