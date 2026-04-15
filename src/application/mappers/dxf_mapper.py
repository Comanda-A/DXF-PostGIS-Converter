from __future__ import annotations

from ...domain.entities import DXFBase, DXFDocument, DXFLayer, DXFEntity
from ...application.dtos import DXFBaseDTO, DXFDocumentDTO, DXFLayerDTO, DXFEntityDTO

class DXFMapper:
    
    @classmethod
    def to_dto(cls, obj: DXFBase | list[DXFBase]) -> DXFBaseDTO | list[DXFBaseDTO]:
        if isinstance(obj, list):
            return [cls._single_to_dto(item) for item in obj]
        return cls._single_to_dto(obj)
    
    @classmethod
    def _single_to_dto(cls, obj: DXFBase) -> DXFBaseDTO:
        """Преобразование одного объекта в DTO"""
        
        if isinstance(obj, DXFDocument):
            return DXFDocumentDTO(
                id=obj.id,
                selected=obj.is_selected,
                filename=obj.filename,
                filepath=obj.filepath,
                layers=cls.to_dto(list(obj.layers.values()))
            )
        elif isinstance(obj, DXFLayer):
            return DXFLayerDTO(
                id=obj.id,
                selected=obj.is_selected,
                name=obj.name,
                entities=cls.to_dto(list(obj.entities.values()))
            )
        elif isinstance(obj, DXFEntity):
            return DXFEntityDTO(
                id=obj.id,
                selected=obj.is_selected,
                name=obj.name,
                typename=obj.entity_type.value,
                attributes=obj.attributes,
                geometries=obj.geometries
            )
        else:
            raise ValueError(f"Unknown entity type: {type(obj)}")
