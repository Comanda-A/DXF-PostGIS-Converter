# -*- coding: utf-8 -*-
"""
DXF Domain - работа с DXF документами.

Содержит:
- DxfDocument: Загрузка и работа с DXF документами
- EntitySelector: Выбор сущностей по критериям
- DXFHandlerCore: Низкоуровневая работа с DXF (без UI)
"""

from .dxf_document import DxfDocument
from .entity_selector import EntitySelector
from .dxf_handler import DXFHandlerCore

__all__ = [
    'DxfDocument',
    'EntitySelector',
    'DXFHandlerCore',
]
