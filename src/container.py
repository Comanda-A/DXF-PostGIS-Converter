# -*- coding: utf-8 -*-
"""
Dependency Container - контейнер зависимостей для Dependency Injection.

Централизованное создание и управление зависимостями.
"""

from typing import Optional

from .application import SettingsService, ImportService, ExportService, SchemaService
from .infrastructure.database import DatabaseConnection, DxfRepository
from .domain.dxf import EntitySelector


class DependencyContainer:
    """
    Контейнер зависимостей.
    
    Создаёт и хранит экземпляры сервисов для инъекции в диалоги.
    Реализует паттерн Composition Root.
    """
    
    _instance: Optional['DependencyContainer'] = None
    
    def __new__(cls) -> 'DependencyContainer':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Infrastructure
        self._db_connection: Optional[DatabaseConnection] = None
        self._repository: Optional[DxfRepository] = None
        
        # Application
        self._settings_service: Optional[SettingsService] = None
        self._import_service: Optional[ImportService] = None
        self._export_service: Optional[ExportService] = None
        self._schema_service: Optional[SchemaService] = None
        
        # Domain
        self._entity_selector: Optional[EntitySelector] = None
        
        self._initialized = True
    
    @classmethod
    def instance(cls) -> 'DependencyContainer':
        """Получить экземпляр контейнера (singleton)."""
        return cls()
    
    # ========== Infrastructure ==========
    
    @property
    def db_connection(self) -> DatabaseConnection:
        """Подключение к БД."""
        if self._db_connection is None:
            self._db_connection = DatabaseConnection.instance()
        return self._db_connection
    
    @property
    def repository(self) -> DxfRepository:
        """Репозиторий данных."""
        if self._repository is None:
            self._repository = DxfRepository(self.db_connection)
        return self._repository
    
    # ========== Application ==========
    
    @property
    def settings_service(self) -> SettingsService:
        """Сервис настроек."""
        if self._settings_service is None:
            self._settings_service = SettingsService.instance()
        return self._settings_service
    
    @property
    def import_service(self) -> ImportService:
        """Сервис импорта."""
        if self._import_service is None:
            self._import_service = ImportService(
                connection=self.db_connection,
                repository=self.repository
            )
        return self._import_service
    
    @property
    def export_service(self) -> ExportService:
        """Сервис экспорта."""
        if self._export_service is None:
            self._export_service = ExportService(
                db_connection=self.db_connection,
                repository=self.repository
            )
        return self._export_service
    
    @property
    def schema_service(self) -> SchemaService:
        """Сервис работы со схемами."""
        if self._schema_service is None:
            self._schema_service = SchemaService(
                connection=self.db_connection,
                repository=self.repository,
                settings_service=self.settings_service
            )
        return self._schema_service
    
    # ========== Domain ==========
    
    @property
    def entity_selector(self) -> EntitySelector:
        """Селектор сущностей."""
        if self._entity_selector is None:
            self._entity_selector = EntitySelector()
        return self._entity_selector
    
    # ========== Lifecycle ==========
    
    def reset(self) -> None:
        """Сбросить все зависимости (для тестов)."""
        self._db_connection = None
        self._repository = None
        self._settings_service = None
        self._import_service = None
        self._export_service = None
        self._schema_service = None
        self._entity_selector = None
    
    def shutdown(self) -> None:
        """Корректное завершение работы."""
        if self._db_connection:
            self._db_connection.close()
