# -*- coding: utf-8 -*-
"""
Export Service - Application Layer.

Координирует процесс экспорта из PostgreSQL/PostGIS в DXF файлы.
Не содержит UI-логику — только бизнес-процессы.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, List, Any

from ..domain.models.config import ExportConfig
from ..domain.models.result import ExportResult, ValidationResult
from ..infrastructure.database import DatabaseConnection, DxfRepository
from ..logger.logger import Logger


class ExportDestination(Enum):
    """Назначение экспорта."""
    FILE = "file"
    QGIS = "qgis"
    MEMORY = "memory"


@dataclass
class ExportRequest:
    """Запрос на экспорт из БД."""
    file_id: int
    destination: ExportDestination = ExportDestination.FILE
    output_path: Optional[str] = None  # Для FILE destination
    file_name: Optional[str] = None


@dataclass
class ExportEntitiesRequest:
    """Запрос на экспорт выбранных сущностей."""
    source_file: str
    output_file: str
    entity_handles: List[str]


class ExportService:
    """
    Сервис экспорта DXF — Application Layer Use Case.
    
    Координирует:
    - Валидацию параметров экспорта
    - Получение данных из БД
    - Создание DXF файла
    - Отчёт о результате
    
    НЕ содержит:
    - UI-диалоги (показ ошибок, выбор файла)
    - Прямой доступ к виджетам
    """
    
    def __init__(
        self,
        db_connection: DatabaseConnection,
        repository: DxfRepository
    ):
        self._db_connection = db_connection
        self._repository = repository
    
    def validate_export_config(self, config: ExportConfig) -> ValidationResult:
        """
        Валидация конфигурации экспорта.
        
        Args:
            config: Конфигурация экспорта
            
        Returns:
            Результат валидации с ошибками (если есть)
        """
        errors = []
        warnings = []
        
        # Проверка подключения
        if not config.connection:
            errors.append("Не указано подключение к БД")
        else:
            if not config.connection.host:
                errors.append("Не указан хост БД")
            if not config.connection.database:
                errors.append("Не указана база данных")
            if not config.connection.username:
                errors.append("Не указан пользователь")
            if not config.connection.password:
                errors.append("Не указан пароль")
        
        # Проверка file_id
        if not config.file_id or config.file_id <= 0:
            errors.append("Не указан ID файла для экспорта")
        
        # Проверка пути для FILE destination
        if config.destination == "file" and not config.output_path:
            warnings.append("Путь для сохранения файла не указан — будет запрошен у пользователя")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def export_from_database(
        self,
        config: ExportConfig,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> ExportResult:
        """
        Экспорт DXF файла из базы данных.
        
        Args:
            config: Конфигурация экспорта
            progress_callback: Callback для прогресса (percent, message)
            
        Returns:
            Результат экспорта
        """
        def report_progress(percent: int, message: str):
            if progress_callback:
                progress_callback(percent, message)
            Logger.log_message(f"Export progress: {percent}% - {message}")
        
        # Валидация
        report_progress(5, "Проверка параметров...")
        validation = self.validate_export_config(config)
        if not validation.is_valid:
            return ExportResult(
                success=False,
                message="; ".join(validation.errors)
            )
        
        try:
            # Подключение к БД
            report_progress(10, "Подключение к базе данных...")
            session = self._db_connection.connect(config.connection)
            
            if not session:
                return ExportResult(
                    success=False,
                    message="Не удалось подключиться к базе данных"
                )
            
            try:
                # Получение файла
                report_progress(30, "Получение данных файла...")
                file_record = self._repository.get_file_by_id(
                    session, 
                    config.file_id,
                    schema=config.file_schema
                )
                
                if not file_record:
                    return ExportResult(
                        success=False,
                        message=f"Файл с ID {config.file_id} не найден в базе данных"
                    )
                
                report_progress(50, "Подготовка контента...")
                file_content = file_record.file_content
                file_name = config.file_name or file_record.filename
                
                # Определение пути
                output_path = self._resolve_output_path(config, file_name)
                if not output_path:
                    return ExportResult(
                        success=False,
                        message="Путь для сохранения не определён"
                    )
                
                # Запись файла
                report_progress(70, "Сохранение файла...")
                self._write_file(output_path, file_content)
                
                report_progress(100, "Экспорт завершён")
                
                return ExportResult(
                    success=True,
                    message=f"Файл {file_name} экспортирован успешно",
                    output_path=output_path,
                    entities_exported=0  # TODO: можно получить из метаданных
                )
                
            finally:
                session.close()
                
        except Exception as e:
            Logger.log_error(f"Export error: {e}")
            return ExportResult(
                success=False,
                message=str(e)
            )
    
    def export_selected_entities(
        self,
        request: ExportEntitiesRequest,
        dxf_handler: Any,  # DXFHandler из presentation layer
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> ExportResult:
        """
        Экспорт выбранных сущностей в новый DXF файл.
        
        Делегирует работу DXFHandler.save_selected_entities(), который использует
        ezdxf.xref.write_block для корректного копирования сущностей вместе со
        всеми зависимыми ресурсами (слои, стили, типы линий и т.д.).
        
        Args:
            request: Запрос на экспорт сущностей
            dxf_handler: Обработчик DXF с загруженными документами
            progress_callback: Callback для прогресса
            
        Returns:
            Результат экспорта
        """
        def report_progress(percent: int, message: str):
            if progress_callback:
                progress_callback(percent, message)
        
        try:
            report_progress(10, "Подготовка к экспорту...")
            
            report_progress(50, "Экспорт сущностей...")
            success = dxf_handler.save_selected_entities(
                request.source_file, request.output_file
            )
            
            report_progress(100, "Экспорт завершён")
            
            if success:
                return ExportResult(
                    success=True,
                    output_path=request.output_file,
                    message="Экспорт выбранных сущностей завершён успешно"
                )
            else:
                return ExportResult(
                    success=False,
                    message="Не удалось экспортировать выбранные сущности"
                )
            
        except Exception as e:
            Logger.log_error(f"Export entities error: {e}")
            return ExportResult(
                success=False,
                message=str(e)
            )
    
    def _resolve_output_path(self, config: ExportConfig, file_name: str) -> Optional[str]:
        """Определяет путь для сохранения файла."""
        import os
        import tempfile
        
        if config.output_path:
            return config.output_path
        
        if config.destination == "qgis":
            # Временный файл для QGIS
            temp_dir = tempfile.gettempdir()
            return os.path.join(temp_dir, file_name)
        
        # Для "file" — путь должен быть запрошен у пользователя (UI layer)
        return None
    
    def _write_file(self, path: str, content: bytes) -> None:
        """Записывает файл на диск."""
        import os
        
        # Создаём директорию если нужно
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        
        with open(path, 'wb') as f:
            f.write(content)
        
        Logger.log_message(f"File written to {path}")
