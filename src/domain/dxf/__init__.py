# -*- coding: utf-8 -*-
"""
DXF Domain - работа с DXF документами.

Содержит:
- DxfDocument: Загрузка и работа с DXF документами
- EntitySelector: Выбор сущностей по критериям
- DXFHandler: Низкоуровневая работа с DXF (без UI)
"""

from .dxf_document import DxfDocument
from .entity_selector import EntitySelector
from .dxf_handler import DXFHandler

__all__ = [
    'DxfDocument',
    'EntitySelector',
    'DXFHandler',
]
