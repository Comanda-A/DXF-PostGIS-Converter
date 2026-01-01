# -*- coding: utf-8 -*-
"""
DXF Domain - работа с DXF документами.
"""

from .dxf_document import DxfDocument
from .entity_selector import EntitySelector

__all__ = [
    'DxfDocument',
    'EntitySelector',
]
