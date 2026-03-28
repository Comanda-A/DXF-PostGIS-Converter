
from typing import Dict, List, Optional
from uuid import UUID
from ...domain.entities import DXFBase, DXFEntity

class DXFLayer(DXFBase):
    
    def __init__(
        self,
        document_id: UUID,
        name: str,
        schema_name: str,
        table_name: str,
        id: Optional[UUID] = None,
        selected: bool = True,
        entities: Optional[List[DXFEntity]] = None
    ):
        super().__init__(id, selected)
        self._document_id = document_id
        self._name = name
        self._schema_name = schema_name
        self._table_name = table_name

        self._entities = {entity.id: entity for entity in (entities or [])}
    
    @classmethod
    def create(
        cls,
        document_id: UUID,
        name: str,
        schema_name: str = "",
        table_name: str = "",
        id: Optional[UUID] = None,
        selected: bool = True,
        entities: Optional[List[DXFEntity]] = None
    ) -> 'DXFLayer':
        return cls(document_id, name, schema_name, table_name, id, selected, entities)

    @property
    def document_id(self) -> UUID:
        return self._document_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def schema_name(self) -> str:
        return self._schema_name

    @property
    def table_name(self) -> str:
        return self._table_name

    @property
    def entities(self) -> Dict[int, DXFEntity]:
        """id: entity"""
        return self._entities

    def add_entities(self, entities: List[DXFEntity]):
        for entity in entities:
            self._entities[entity.id] = entity
    
    def find_entity_by_id(self, entity_id: int) -> Optional[DXFEntity]:
        return self._entities.get(entity_id)
    
    def find_entity_by_name(self, name: str) -> Optional[DXFEntity]:
        for entity in self._entities.values():
            if entity.name == name:
                return entity
        return None
    
    def clear(self, recursive: bool = True):
        self.entities.clear()
        self._parent = None
        self._name = None