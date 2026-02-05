# -*- coding: utf-8 -*-
"""
Config DTOs - конфигурации для операций импорта/экспорта.

Содержит доменные модели данных: ConnectionSettings, SchemaSettings,
ImportConfig, ExportConfig. Эти классы — чистые DTO без UI-зависимостей.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class ConnectionSettings:
    """Настройки подключения к базе данных."""
    host: str = 'none'
    port: str = '5432'
    database: str = 'none'
    username: str = 'none'
    password: str = ''

    @property
    def is_configured(self) -> bool:
        """Проверяет, настроено ли подключение."""
        return self.database != 'none' and self.username != 'none'

    @property
    def display_name(self) -> str:
        """Возвращает отображаемое имя подключения."""
        return f"{self.host}:{self.port}/{self.database}"


@dataclass
class SchemaSettings:
    """Настройки схем базы данных."""
    layer_schema: str = 'layer_schema'
    file_schema: str = 'file_schema'
    export_layers_only: bool = False
    custom_filename: str = ''


@dataclass
class ImportConfig:
    """Конфигурация импорта DXF → PostGIS."""
    
    # Подключение к БД
    connection: ConnectionSettings
    
    # Схемы
    layer_schema: str = 'layer_schema'
    file_schema: str = 'file_schema'
    
    # Режим импорта
    mapping_mode: str = 'always_overwrite'
    export_layers_only: bool = False
    
    # Имя файла
    custom_filename: Optional[str] = None
    
    # Маппинг столбцов
    column_mappings: Dict[str, Any] = field(default_factory=dict)
    
    # Создавать ли превью при импорте
    generate_preview: bool = True
    
    @property
    def is_valid(self) -> bool:
        """Базовая проверка валидности конфигурации."""
        return (
            self.connection.is_configured and
            bool(self.layer_schema) and
            (self.export_layers_only or bool(self.file_schema))
        )


@dataclass
class ExportConfig:
    """Конфигурация экспорта PostGIS → DXF."""
    
    # Подключение к БД
    connection: ConnectionSettings
    
    # ID файла в БД
    file_id: int
    
    # Место назначения: "file" или "qgis"
    destination: str = "file"
    
    # Путь для сохранения (если destination = "file")
    output_path: Optional[str] = None
    
    # Имя файла
    file_name: Optional[str] = None
    
    # Схема файлов
    file_schema: str = 'file_schema'
    
    @property
    def is_valid(self) -> bool:
        """Базовая проверка валидности конфигурации."""
        return (
            self.connection.is_configured and
            self.file_id > 0 and
            self.destination in ("file", "qgis")
        )
