
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
        from .postgis_connection import PostGISConnection
        return PostGISConnection
    if name == 'PostGISDocumentRepository':
        from .postgis_document_repository import PostGISDocumentRepository
        return PostGISDocumentRepository
    if name == 'PostGISContentRepository':
        from .postgis_content_repository import PostGISContentRepository
        return PostGISContentRepository
    if name == 'PostGISLayerRepository':
        from .postgis_layer_repository import PostGISLayerRepository
        return PostGISLayerRepository
    if name == 'PostGISEntityRepository':
        from .postgis_entity_repository import PostGISEntityRepository
        return PostGISEntityRepository
    if name == 'PostGISEntityConverter':
        from .postgis_entity_converter import PostGISEntityConverter
        return PostGISEntityConverter
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
