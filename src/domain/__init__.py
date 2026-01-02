# -*- coding: utf-8 -*-
"""
Domain Layer - чистая бизнес-логика.

Содержит:
- dxf/ - работа с DXF документами
- models/ - доменные модели
- converters/ - конвертация между форматами
"""

from .dxf import DxfDocument, EntitySelector
from .models import ImportConfig, ImportResult, ValidationResult
from .converters import DXFToPostGISConverter, DXFEntitiesExporter

__all__ = [
    'DxfDocument',
    'EntitySelector',
    'ImportConfig',
    'ImportResult',
    'ValidationResult',
    'DXFToPostGISConverter',
    'DXFEntitiesExporter',
]
