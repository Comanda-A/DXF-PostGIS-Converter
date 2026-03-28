
from abc import ABC, abstractmethod
from ...domain.value_objects import Result
from ...domain.repositories import (
    IConnection,
    IDocumentRepository,
    IContentRepository,
    ILayerRepository,
    IEntityRepository
)

class IRepositoryFactory(ABC):
    """Фабрика для создания репозиториев"""
    
    @abstractmethod
    def get_document_repository(
        self,
        connection: IConnection,
        schema: str = "file_schema",
        table_name: str = "files"
    ) -> Result[IDocumentRepository]:
        pass

    @abstractmethod
    def get_content_repository(
        self,
        connection: IConnection,
        schema: str = "file_schema",
        table_name: str = "content"
    ) -> Result[IContentRepository]:
        pass

    @abstractmethod
    def get_layer_repository(
        self,
        connection: IConnection,
        schema: str = "file_schema",
        table_name: str = "layers"
    ) -> Result[ILayerRepository]:
        pass

    @abstractmethod
    def get_entity_repository(
        self,
        connection: IConnection,
        schema: str = "layer_schema",
        table_name: str = "layer_name"
    ) -> Result[IEntityRepository]:
        pass
