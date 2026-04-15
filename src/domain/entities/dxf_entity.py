
from typing import Any, Dict, Optional

from uuid import UUID
from ...domain.entities import DXFBase
from ...domain.value_objects import DxfEntityType

class DXFEntity(DXFBase):
        
    def __init__(
        self,
        id: Optional[UUID] = None,
        selected: bool = True,
        entity_type: DxfEntityType = DxfEntityType.UNKNOWN,
        name: str = "",
        attributes: Optional[Dict[str, Any]] = None,
        geometries: Optional[Dict[str, Any]] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(id, selected)
        self._entity_type = entity_type
        self._name = name
        self._attributes = attributes or {}
        self._geometries = geometries or {}
        self._extra_data = extra_data or {}
    
    @classmethod
    def create(
        cls,
        id: Optional[UUID] = None,
        selected: bool = True,
        entity_type: DxfEntityType = DxfEntityType.UNKNOWN,
        name: str = "",
        attributes: Optional[Dict[str, Any]] = None,
        geometries: Optional[Dict[str, Any]] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> 'DXFEntity':
        return cls(id, selected, entity_type, name, attributes, geometries, extra_data)

    @property
    def entity_type(self) -> DxfEntityType:
        return self._entity_type

    @property
    def name(self) -> str:
        return self._name

    @property
    def attributes(self) -> Dict[str, Any]:
        return self._attributes
    
    @property
    def geometries(self) -> Dict[str, Any]:
        return self._geometries

    @property
    def extra_data(self) -> Dict[str, Any]:
        return self._extra_data

    def add_attributes(self, attributes: Dict[str, Any]):
        self._attributes.update(attributes)

    def add_geometries(self, geometries: Dict[str, Any]):
        self._geometries.update(geometries)

    def add_extra_data(self, extra_data: Dict[str, Any]):
        self._extra_data.update(extra_data)

    def clear(self, recursive: bool = True):
        self._name = ""
        self._parent = None
        self._attributes.clear()
        self._geometries.clear()