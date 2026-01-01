# -*- coding: utf-8 -*-
"""
Infrastructure Layer - реализации работы с внешними системами.

Содержит:
- database/ - работа с PostgreSQL/PostGIS
- dxf/ - чтение/запись DXF файлов  
- qgis/ - QGIS-специфичная инфраструктура
"""

from .database import DatabaseConnection, DxfRepository

__all__ = [
    'DatabaseConnection',
    'DxfRepository',
]
