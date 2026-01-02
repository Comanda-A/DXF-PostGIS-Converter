# -*- coding: utf-8 -*-
"""
Application Layer - Use Cases и сервисы координации бизнес-логики.
"""

# Lazy imports to avoid circular dependencies
# Import only what doesn't cause cycles
from .settings_service import SettingsService, ConnectionSettings, SchemaSettings

__all__ = [
    'SettingsService',
    'ConnectionSettings', 
    'SchemaSettings',
    'ImportService',
    'ExportService',
]


def __getattr__(name: str):
    """Lazy loading of services to avoid circular imports."""
    if name == 'ImportService':
        from .import_service import ImportService
        return ImportService
    elif name == 'ExportService':
        from .export_service import ExportService
        return ExportService
    elif name == 'ExportDestination':
        from .export_service import ExportDestination
        return ExportDestination
    elif name == 'ExportRequest':
        from .export_service import ExportRequest
        return ExportRequest
    elif name == 'ExportEntitiesRequest':
        from .export_service import ExportEntitiesRequest
        return ExportEntitiesRequest
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
