# -*- coding: utf-8 -*-
"""
Import Service - координатор процесса импорта DXF → PostGIS.

Application Layer сервис. Не содержит UI-логики!
"""

import os
import tempfile
from typing import Optional, Callable, List, Dict, Any

from ..domain.dxf import DxfDocument, EntitySelector
from ..domain.models import ImportConfig, ImportResult, ValidationResult
from ..domain.converters import DXFToPostGISConverter
from ..infrastructure.database import DatabaseConnection, DxfRepository
from ..logger.logger import Logger


# Тип callback для прогресса: (percent: int, message: str)
ProgressCallback = Callable[[int, str], None]


class ImportService:
    """
    Координатор процесса импорта DXF → PostGIS.
    
    Не содержит UI-логики! Вся координация бизнес-процесса импорта.
    """
    
    def __init__(
        self,
        connection: Optional[DatabaseConnection] = None,
        repository: Optional[DxfRepository] = None,
    ):
        """
        Args:
            connection: Подключение к БД
            repository: Репозиторий для работы с данными
        """
        self._connection = connection or DatabaseConnection.instance()
        self._repository = repository or DxfRepository(self._connection)
        self._converter = DXFToPostGISConverter()
    
    def validate_config(self, config: ImportConfig) -> ValidationResult:
        """
        Валидировать конфигурацию импорта.
        
        Args:
            config: Конфигурация для проверки
            
        Returns:
            Результат валидации
        """
        result = ValidationResult()
        
        # Проверка подключения
        if not config.connection.is_configured:
            result.add_error("Не настроено подключение к базе данных")
        
        # Проверка схем
        if not config.layer_schema:
            result.add_error("Не указана схема для слоёв")
        
        if not config.export_layers_only and not config.file_schema:
            result.add_error("Не указана схема для файлов")
        
        # Предупреждения
        if config.mapping_mode not in ('always_overwrite', 'geometry', 'notes', 'both'):
            result.add_warning(f"Неизвестный режим маппирования: {config.mapping_mode}")
        
        return result
    
    def get_available_schemas(self, config: ImportConfig) -> List[str]:
        """
        Получить список доступных схем.
        
        Args:
            config: Конфигурация с параметрами подключения
            
        Returns:
            Список схем
        """
        session = self._connection.connect(config.connection)
        if not session:
            return []
        
        try:
            return self._repository.get_schemas(session)
        finally:
            session.close()
    
    def create_schema(self, config: ImportConfig, schema_name: str) -> bool:
        """
        Создать новую схему.
        
        Args:
            config: Конфигурация с параметрами подключения
            schema_name: Имя схемы
            
        Returns:
            True если успешно
        """
        session = self._connection.connect(config.connection)
        if not session:
            return False
        
        try:
            return self._repository.create_schema(session, schema_name)
        finally:
            session.close()
    
    def import_dxf(
        self,
        file_path: str,
        config: ImportConfig,
        entities_by_layer: Optional[Dict[str, List[Any]]] = None,
        progress_callback: Optional[ProgressCallback] = None
    ) -> ImportResult:
        """
        Импортировать DXF файл в PostGIS.
        
        Args:
            file_path: Путь к DXF файлу
            config: Конфигурация импорта
            entities_by_layer: Сущности для импорта (опционально, если None - все)
            progress_callback: Callback для обновления прогресса
            
        Returns:
            Результат импорта
        """
        def report_progress(percent: int, message: str):
            if progress_callback:
                progress_callback(percent, message)
            Logger.log_message(f"[{percent}%] {message}")
        
        # Валидация
        validation = self.validate_config(config)
        if not validation.is_valid:
            return ImportResult.error_result(
                "Ошибка конфигурации: " + "; ".join(validation.errors)
            )
        
        report_progress(5, "Подключение к базе данных...")
        
        # Подключаемся к БД
        session = self._connection.connect(config.connection)
        if not session:
            return ImportResult.error_result("Не удалось подключиться к базе данных")
        
        try:
            # Проверяем PostGIS
            report_progress(10, "Проверка расширения PostGIS...")
            if not self._connection.ensure_postgis_extension(session):
                return ImportResult.error_result("Расширение PostGIS недоступно")
            
            # Убеждаемся что таблица dxf_files существует (для ForeignKey в таблицах слоёв)
            report_progress(12, "Проверка структуры БД...")
            if not self._repository.ensure_file_table(session, config.file_schema):
                return ImportResult.error_result("Не удалось создать таблицу dxf_files")
            
            # Загружаем DXF если не переданы сущности
            if entities_by_layer is None:
                report_progress(15, "Чтение DXF файла...")
                document = DxfDocument(file_path)
                if not document.is_loaded:
                    return ImportResult.error_result("Не удалось загрузить DXF файл")
                entities_by_layer = document.get_layers()
            
            # Определяем имя файла
            original_filename = os.path.basename(file_path)
            filename_for_db = config.custom_filename or original_filename
            if not filename_for_db.lower().endswith('.dxf'):
                filename_for_db += '.dxf'
            
            Logger.log_message(f"Импорт файла: {filename_for_db}")
            Logger.log_message(f"Слоёв для импорта: {len(entities_by_layer)}")
            
            file_record = None
            file_id = None
            
            # Создаём запись о файле (если нужно)
            if not config.export_layers_only:
                report_progress(20, "Сохранение файла в базу данных...")
                
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                
                file_record = self._repository.create_file(
                    session, filename_for_db, file_content, config.file_schema
                )
                
                if not file_record:
                    return ImportResult.error_result("Не удалось сохранить файл в базу данных")
                
                file_id = file_record.id
            
            # Импортируем слои
            report_progress(30, "Импорт слоёв...")
            
            total_layers = len(entities_by_layer)
            layers_imported = 0
            total_entities = 0
            layer_errors = {}
            
            for i, (layer_name, entities) in enumerate(entities_by_layer.items()):
                layer_progress = 30 + int((i / max(total_layers, 1)) * 60)
                report_progress(layer_progress, f"Обработка слоя: {layer_name}")
                
                try:
                    # Создаём таблицу слоя
                    layer_class = self._repository.create_layer_table(
                        session, layer_name, config.layer_schema, config.file_schema
                    )
                    
                    if not layer_class:
                        layer_errors[layer_name] = "Не удалось создать таблицу"
                        continue
                    
                    # Очищаем существующие данные
                    if config.mapping_mode == 'always_overwrite':
                        self._repository.clear_layer(session, layer_class, file_id)
                    
                    # Конвертируем и вставляем сущности
                    postgis_entities = self._convert_entities(entities)
                    
                    if postgis_entities:
                        success = self._repository.insert_entities(
                            session, layer_class, postgis_entities, file_id
                        )
                        
                        if success:
                            layers_imported += 1
                            total_entities += len(postgis_entities)
                        else:
                            layer_errors[layer_name] = "Ошибка вставки данных"
                    
                except Exception as e:
                    layer_errors[layer_name] = str(e)
                    Logger.log_error(f"Ошибка импорта слоя '{layer_name}': {str(e)}")
            
            report_progress(95, "Завершение импорта...")
            
            # Формируем результат
            if layers_imported > 0:
                return ImportResult(
                    success=True,
                    message=f"Импортировано {layers_imported} слоёв, {total_entities} сущностей",
                    files_imported=1 if file_record else 0,
                    layers_imported=layers_imported,
                    entities_imported=total_entities,
                    layer_errors=layer_errors
                )
            else:
                return ImportResult.error_result(
                    "Не удалось импортировать ни один слой"
                )
            
        except Exception as e:
            Logger.log_error(f"Ошибка импорта: {str(e)}")
            return ImportResult.error_result(f"Ошибка импорта: {str(e)}")
        
        finally:
            session.close()
    
    def _convert_entities(self, entities) -> List[Dict[str, Any]]:
        """Конвертировать DXF сущности в формат PostGIS."""
        result = []
        entities_list = list(entities)  # Ensure entities is a list
        
        for entity in entities_list:
            try:
                postgis_entity = self._converter.convert_entity_to_postgis(entity)
                if postgis_entity:
                    result.append(postgis_entity)
            except Exception as e:
                Logger.log_warning(f"Ошибка конвертации сущности: {str(e)}")
        
        return result
