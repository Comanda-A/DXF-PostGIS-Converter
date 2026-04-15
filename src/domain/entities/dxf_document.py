
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
from ...domain.entities import DXFBase, DXFLayer, DXFContent

class DXFDocument(DXFBase):
    
    def __init__(
        self, 
        id: Optional[UUID] = None,
        selected: bool = True,
        filename: str = "",
        filepath: str = "",
        layers: Optional[List[DXFLayer]] = None,
        upload_date: Optional[datetime] = None,
        update_date: Optional[datetime] = None,
        content: Optional[DXFContent] = None
    ):
        super().__init__(id, selected)
        self._filename = filename
        self._upload_date = upload_date
        self._update_date = update_date

        self._content = content
        self._filepath = filepath
        self._layers = {layer.id: layer for layer in (layers or [])}
    
    @classmethod
    def create(
        cls, 
        id: Optional[UUID] = None,
        selected: bool = True,
        filename: str = "",
        filepath: str = "",
        layers: Optional[List[DXFLayer]] = None,
        upload_date: Optional[datetime] = None,
        update_date: Optional[datetime] = None,
        content: Optional[DXFContent] = None
    ) -> 'DXFDocument':
        return cls(id, selected, filename, filepath, layers, upload_date, update_date, content)

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def filepath(self) -> str:
        return self._filepath
    
    @property
    def layers(self) -> Dict[int, DXFLayer]:
        """id: layer"""
        return self._layers
    
    @property
    def upload_date(self) -> Optional[datetime]:
        return self._upload_date
    
    @property
    def update_date(self) -> Optional[datetime]:
        return self._update_date
    
    @property
    def content(self) -> Optional[DXFContent]:
        return self._content

    def add_content(self, content: DXFContent):
        self._content = content

    def add_layers(self, layers: List[DXFLayer]):
        for layer in layers:
            self._layers[layer.id] = layer

    def get_layer_by_id(self, layer_id: int) -> Optional[DXFLayer]:
        return self._layers.get(layer_id)
    
    def get_layer_by_name(self, name: str) -> Optional[DXFLayer]:
        for layer in self._layers.values():
            if layer.name == name:
                return layer
        return None

    def remove_layer(self, layer: DXFLayer, recursive: bool = False) -> bool:
        if layer.id in self._layers:
            if recursive:
                self._layers[layer.id].clear()
            del self._layers[layer.id]
            return True
        return False

    def clear(self):
        self._layers.clear()
        self._filepath = ""
        self._filename = ""