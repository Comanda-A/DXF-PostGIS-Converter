# -*- coding: utf-8 -*-
"""
Domain Layer - чистая бизнес-логика.

Содержит:
- dxf/ - работа с DXF документами
- models/ - доменные модели (ConnectionSettings, ImportConfig, ExportConfig и др.)
- converters/ - конвертация между форматами
"""

from .dxf import DxfDocument, EntitySelector
from .models import ConnectionSettings, SchemaSettings, ImportConfig, ImportResult, ValidationResult
from .converters import DXFToPostGISConverter

__all__ = [
    'DxfDocument',
    'EntitySelector',
    'ConnectionSettings',
    'SchemaSettings',
    'ImportConfig',
    'ImportResult',
    'ValidationResult',
    'DXFToPostGISConverter',
]
