# -*- coding: utf-8 -*-
"""
DXF Domain - работа с DXF документами (чистая логика без UI).

Содержит:
- DxfDocument: Загрузка и работа с DXF документами
- EntitySelector: Выбор сущностей по критериям

DXFHandler перенесён в presentation layer (src/presentation/dxf_handler.py),
т.к. зависит от PyQt и UI-виджетов.
"""

from .dxf_document import DxfDocument
from .entity_selector import EntitySelector

__all__ = [
    'DxfDocument',
    'EntitySelector',
]
