# -*- coding: utf-8 -*-
"""
Domain Layer - чистая бизнес-логика.

Содержит:
- dxf/ - работа с DXF документами
- models/ - доменные модели
"""

from .dxf import DxfDocument, EntitySelector
from .models import ImportConfig, ImportResult, ValidationResult

__all__ = [
    'DxfDocument',
    'EntitySelector',
    'ImportConfig',
    'ImportResult',
    'ValidationResult',
]
