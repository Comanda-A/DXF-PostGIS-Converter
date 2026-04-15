
from typing import Optional
from uuid import UUID
from ...domain.entities import DXFBase

class DXFContent(DXFBase):
        
    def __init__(
        self,
        document_id: UUID,
        content: bytes,
        id: Optional[UUID] = None,
    ):
        super().__init__(id, True)
        self._document_id = document_id
        self._content = content
    
    @classmethod
    def create(
        cls,
        document_id: UUID,
        content: bytes,
        id: Optional[UUID] = None,
    ) -> 'DXFContent':
        return cls(document_id, content, id)

    @property
    def document_id(self) -> UUID:
        return self._document_id

    @property
    def content(self) -> bytes:
        return self._content