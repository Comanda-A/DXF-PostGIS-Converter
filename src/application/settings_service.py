# -*- coding: utf-8 -*-
"""
Settings Service - централизованное управление настройками плагина.

Объединяет работу с:
- Настройками подключения к БД
- Настройками схем
- Пользовательскими настройками (логирование, язык)
"""

from typing import Optional
from qgis.core import QgsSettings

# Импортируем доменные модели — ConnectionSettings и SchemaSettings
# определены в domain layer как чистые DTO
from ..domain.models.config import ConnectionSettings, SchemaSettings


class SettingsService:
    """
    Централизованное управление настройками плагина.
    
    Singleton-сервис для работы с QgsSettings.
    Обеспечивает единую точку доступа к настройкам.
    """
    
    _instance: Optional['SettingsService'] = None
    
    # Ключи настроек
    class Keys:
        # Подключение к БД
        LAST_HOST = "DXFPostGIS/lastConnection/host"
        LAST_PORT = "DXFPostGIS/lastConnection/port"
        LAST_DATABASE = "DXFPostGIS/lastConnection/database"
        LAST_USERNAME = "DXFPostGIS/lastConnection/username"
        LAST_PASSWORD = "DXFPostGIS/lastConnection/password"
        
        # Схемы
        LAYER_SCHEMA = "DXFPostGIS/lastConnection/layerSchema"
        FILE_SCHEMA = "DXFPostGIS/lastConnection/fileSchema"
        EXPORT_LAYERS_ONLY = "DXFPostGIS/lastConnection/exportLayersOnly"
        CUSTOM_FILENAME = "DXFPostGIS/lastConnection/customFilename"
        
        # Пользовательские настройки
        LOGGING_ENABLED = "DXFPostGISConverter/EnableLogging"
        LANGUAGE = "DXFPostGISConverter/Language"
        GENERATE_PREVIEW = "DXFPostGISConverter/GeneratePreview"
        
        # Сохранённые подключения
        CONNECTIONS = "DXFPostGIS/connections"
    
    def __new__(cls) -> 'SettingsService':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._settings = QgsSettings()
        self._initialized = True
    
    @classmethod
    def instance(cls) -> 'SettingsService':
        """Получить экземпляр сервиса (singleton)."""
        return cls()
    
    # ========== Настройки подключения ==========
    
    def get_last_connection(self) -> ConnectionSettings:
        """Получить последнее использованное подключение к БД."""
        return ConnectionSettings(
            host=self._settings.value(self.Keys.LAST_HOST, 'none'),
            port=self._settings.value(self.Keys.LAST_PORT, '5432'),
            database=self._settings.value(self.Keys.LAST_DATABASE, 'none'),
            username=self._settings.value(self.Keys.LAST_USERNAME, 'none'),
            password=self._settings.value(self.Keys.LAST_PASSWORD, ''),
        )
    
    def save_last_connection(self, settings: ConnectionSettings) -> None:
        """Сохранить настройки подключения к БД."""
        self._settings.setValue(self.Keys.LAST_HOST, settings.host)
        self._settings.setValue(self.Keys.LAST_PORT, settings.port)
        self._settings.setValue(self.Keys.LAST_DATABASE, settings.database)
        self._settings.setValue(self.Keys.LAST_USERNAME, settings.username)
        self._settings.setValue(self.Keys.LAST_PASSWORD, settings.password)
    
    # ========== Настройки схем ==========
    
    def get_schema_settings(self) -> SchemaSettings:
        """Получить настройки схем."""
        return SchemaSettings(
            layer_schema=self._settings.value(self.Keys.LAYER_SCHEMA, 'layer_schema'),
            file_schema=self._settings.value(self.Keys.FILE_SCHEMA, 'file_schema'),
            export_layers_only=self._settings.value(self.Keys.EXPORT_LAYERS_ONLY, False, type=bool),
            custom_filename=self._settings.value(self.Keys.CUSTOM_FILENAME, ''),
        )
    
    def save_schema_settings(self, settings: SchemaSettings) -> None:
        """Сохранить настройки схем."""
        self._settings.setValue(self.Keys.LAYER_SCHEMA, settings.layer_schema)
        self._settings.setValue(self.Keys.FILE_SCHEMA, settings.file_schema)
        self._settings.setValue(self.Keys.EXPORT_LAYERS_ONLY, settings.export_layers_only)
        self._settings.setValue(self.Keys.CUSTOM_FILENAME, settings.custom_filename)
    
    # ========== Пользовательские настройки ==========
    
    def is_logging_enabled(self) -> bool:
        """Проверить, включено ли логирование."""
        return self._settings.value(self.Keys.LOGGING_ENABLED, False, type=bool)
    
    def set_logging_enabled(self, enabled: bool) -> None:
        """Установить состояние логирования."""
        self._settings.setValue(self.Keys.LOGGING_ENABLED, enabled)
    
    def get_language(self) -> str:
        """Получить текущий язык интерфейса."""
        return self._settings.value(self.Keys.LANGUAGE, 'ru')
    
    def set_language(self, language: str) -> None:
        """Установить язык интерфейса."""
        self._settings.setValue(self.Keys.LANGUAGE, language)
    
    def is_preview_enabled(self) -> bool:
        """Проверить, включено ли создание превью при импорте."""
        return self._settings.value(self.Keys.GENERATE_PREVIEW, True, type=bool)
    
    def set_preview_enabled(self, enabled: bool) -> None:
        """Установить состояние создания превью при импорте."""
        self._settings.setValue(self.Keys.GENERATE_PREVIEW, enabled)
    
    # ========== Вспомогательные методы ==========
    
    def get_value(self, key: str, default=None, value_type=None):
        """Получить произвольное значение из настроек."""
        if value_type:
            return self._settings.value(key, default, type=value_type)
        return self._settings.value(key, default)
    
    def set_value(self, key: str, value) -> None:
        """Установить произвольное значение в настройки."""
        self._settings.setValue(key, value)
    
    def remove(self, key: str) -> None:
        """Удалить ключ из настроек."""
        self._settings.remove(key)
