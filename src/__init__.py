
__all__ = [
    'DxfPostGISConverter',
    'Container',
]


def __getattr__(name: str):
    if name == 'DxfPostGISConverter':
        from .dxf_postgis_converter import DxfPostGISConverter
        return DxfPostGISConverter
    if name == 'Container':
        from .container import Container
        return Container
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
