
from .postgis_connection import PostGISConnection
from .postgis_document_repository import PostGISDocumentRepository
from .postgis_content_repository import PostGISContentRepository
from .postgis_layer_repository import PostGISLayerRepository
from .postgis_entity_repository import PostGISEntityRepository
from .postgis_entity_converter import PostGISEntityConverter

__all__ = [
    'PostGISConnection',
    'PostGISDocumentRepository',
    'PostGISContentRepository',
    'PostGISLayerRepository',
    'PostGISEntityRepository',
    'PostGISEntityConverter'
]


def __getattr__(name: str):
    if name == 'PostGISConnection':
        return PostGISConnection
    if name == 'PostGISDocumentRepository':
        return PostGISDocumentRepository
    if name == 'PostGISContentRepository':
        return PostGISContentRepository
    if name == 'PostGISLayerRepository':
        return PostGISLayerRepository
    if name == 'PostGISEntityRepository':
        return PostGISEntityRepository
    if name == 'PostGISEntityConverter':
        return PostGISEntityConverter
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
