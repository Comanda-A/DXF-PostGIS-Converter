# -*- coding: utf-8 -*-
"""
Schema Service - координация работы со схемами.

Application Layer сервис для работы со схемами БД.
Содержит логику поиска с fallback без UI-зависимостей.
"""

from typing import Optional, List, Callable, Any, Dict, TypeVar, TYPE_CHECKING
from dataclasses import dataclass

from ..infrastructure.database import DatabaseConnection, DxfRepository
from ..logger.logger import Logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from .settings_service import SettingsService

# Тип для callback диалога выбора схемы
SchemaDialogCallback = Callable[[List[str]], Optional[str]]

# Generic тип для результата поиска
T = TypeVar('T')


@dataclass
class SchemaSearchResult:
    """Результат поиска в схемах."""
    result: Any
    schema: Optional[str]
    searched_schemas: List[str]


class SchemaService:
    """
    Сервис работы со схемами.
    
    Координирует поиск в схемах с fallback стратегией.
    UI-логика (диалог выбора) передаётся через callback.
    """
    
    DEFAULT_SCHEMAS = ['file_schema', 'public']
    
    def __init__(
        self,
        connection: Optional[DatabaseConnection] = None,
        repository: Optional[DxfRepository] = None,
        settings_service: Optional['SettingsService'] = None
    ):
        """
        Args:
            connection: Подключение к БД
            repository: Репозиторий данных
            settings_service: Сервис настроек (для сохранённых схем)
        """
        self._connection = connection or DatabaseConnection.instance()
        self._repository = repository or DxfRepository(self._connection)
        self._settings = settings_service
    
    def find_in_schemas(
        self,
        session: 'Session',
        search_function: Callable[[type], T],
        preferred_schema: Optional[str] = None,
        schema_dialog_callback: Optional[SchemaDialogCallback] = None
    ) -> SchemaSearchResult:
        """
        Универсальный поиск в схемах с fallback.
        
        Стратегия поиска:
        1. Попробовать preferred_schema (если указана)
        2. Попробовать сохранённую схему из настроек
        3. Попробовать схемы по умолчанию (file_schema, public)
        4. Если schema_dialog_callback задан — показать диалог выбора
        
        Args:
            session: Активная сессия БД
            search_function: Функция поиска, принимающая file_class 
                            и возвращающая результат
            preferred_schema: Предпочтительная схема (опционально)
            schema_dialog_callback: Callback для показа диалога выбора
            
        Returns:
            SchemaSearchResult с результатом и использованной схемой
        """
        from ..infrastructure.database import models
        
        searched = []
        existing_schemas = self._repository.get_schemas(session)
        
        if not existing_schemas:
            Logger.log_warning("Не удалось получить список схем")
            return SchemaSearchResult(result=None, schema=None, searched_schemas=[])
        
        # 1. Пробуем preferred_schema
        if preferred_schema:
            result = self._try_schema(
                session, search_function, preferred_schema, 
                existing_schemas, models
            )
            searched.append(preferred_schema)
            if result is not None:
                return SchemaSearchResult(
                    result=result, schema=preferred_schema, searched_schemas=searched
                )
        
        # 2. Пробуем сохранённую схему
        saved_schema = self._get_saved_schema()
        if saved_schema and saved_schema != preferred_schema:
            result = self._try_schema(
                session, search_function, saved_schema,
                existing_schemas, models
            )
            searched.append(saved_schema)
            if result is not None:
                self._save_schema(saved_schema)
                return SchemaSearchResult(
                    result=result, schema=saved_schema, searched_schemas=searched
                )
        
        # 3. Пробуем схемы по умолчанию
        for default_schema in self.DEFAULT_SCHEMAS:
            if default_schema in searched:
                continue
            result = self._try_schema(
                session, search_function, default_schema,
                existing_schemas, models
            )
            searched.append(default_schema)
            if result is not None:
                Logger.log_message(f"Найдено в схеме '{default_schema}'")
                return SchemaSearchResult(
                    result=result, schema=default_schema, searched_schemas=searched
                )
        
        # 4. Показываем диалог выбора (если есть callback)
        if schema_dialog_callback:
            selected = schema_dialog_callback(existing_schemas)
            if selected:
                result = self._try_schema(
                    session, search_function, selected,
                    existing_schemas, models
                )
                searched.append(selected)
                if result is not None:
                    self._save_schema(selected)
                    Logger.log_message(f"Найдено в выбранной схеме '{selected}'")
                    return SchemaSearchResult(
                        result=result, schema=selected, searched_schemas=searched
                    )
        
        return SchemaSearchResult(result=None, schema=None, searched_schemas=searched)
    
    def _try_schema(
        self,
        session: 'Session',
        search_function: Callable[[type], T],
        schema: str,
        existing_schemas: List[str],
        models
    ) -> Optional[T]:
        """Попробовать поиск в указанной схеме."""
        if schema not in existing_schemas:
            Logger.log_warning(f"Схема '{schema}' не существует")
            return None
        
        try:
            file_class = models.ModelFactory.create_file_table(schema)
            result = search_function(file_class)
            
            # Проверяем, что результат не пустой
            if result is None:
                return None
            if hasattr(result, '__len__') and len(result) == 0:
                return None
            return result
            
        except Exception as e:
            Logger.log_warning(f"Ошибка поиска в схеме '{schema}': {str(e)}")
            return None
    
    def _get_saved_schema(self) -> Optional[str]:
        """Получить сохранённую схему из настроек."""
        if self._settings:
            schema_settings = self._settings.get_schema_settings()
            return schema_settings.file_schema
        
        # Fallback на QgsSettings
        try:
            from qgis.core import QgsSettings
            settings = QgsSettings()
            return settings.value("DXFPostGIS/lastConnection/fileSchema", None)
        except Exception:
            return None
    
    def _save_schema(self, schema: str) -> None:
        """Сохранить схему в настройки."""
        if self._settings:
            # Через SettingsService
            schema_settings = self._settings.get_schema_settings()
            schema_settings.file_schema = schema
            self._settings.save_schema_settings(schema_settings)
        else:
            # Fallback на QgsSettings
            try:
                from qgis.core import QgsSettings
                settings = QgsSettings()
                settings.setValue("DXFPostGIS/lastConnection/fileSchema", schema)
            except Exception:
                pass
    
    def get_effective_schema(
        self,
        session: 'Session',
        preferred_schema: Optional[str] = None
    ) -> Optional[str]:
        """
        Получить эффективную схему с учётом настроек и fallback.
        
        Args:
            session: Активная сессия БД
            preferred_schema: Предпочтительная схема
            
        Returns:
            Имя схемы или None
        """
        existing = self._repository.get_schemas(session)
        
        if preferred_schema and preferred_schema in existing:
            return preferred_schema
        
        saved = self._get_saved_schema()
        if saved and saved in existing:
            return saved
        
        for default in self.DEFAULT_SCHEMAS:
            if default in existing:
                return default
        
        return existing[0] if existing else None
