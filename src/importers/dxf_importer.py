"""
DXF to Database Importer
Handles importing DXF files into PostGIS database.
"""

import os
from typing import Optional, Dict, List
from sqlalchemy.orm import Session, declarative_base, close_all_sessions
from sqlalchemy import create_engine, text, inspect, MetaData, Table

from .converter import DXFToPostGISConverter
from .import_thread import ImportThread
from ..db import models
from ..db.database import DatabaseManager
from ..db.base import Base
from ..logger.logger import Logger
from ..dxf.dxf_handler import DXFHandler


class DXFImporter:
    """
    Handles importing DXF files into PostGIS database.
    """

    def __init__(self):
        self.logger = Logger
        self.db_manager = DatabaseManager()

    def import_dxf_to_database(self, username: str, password: str, host: str, port: str, dbname: str,
                              dxf_handler: DXFHandler, file_path: str, mapping_mode: str = "always_overwrite",
                              layer_schema: str = 'layer_schema', file_schema: str = 'file_schema',
                              export_layers_only: bool = False, custom_filename: str = None,
                              column_mapping_configs: dict = None) -> bool:
        """
        Import DXF file into PostGIS database.

        Args:
            username: Database username
            password: Database password
            host: Database host
            port: Database port
            dbname: Database name
            dxf_handler: DXFHandler instance
            file_path: Path to DXF file
            mapping_mode: Column mapping mode
            layer_schema: Layer schema name
            file_schema: File schema name
            export_layers_only: Whether to export layers only
            custom_filename: Custom filename for DB
            column_mapping_configs: Column mapping configurations

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create database connection
            session = self.db_manager._connect_to_database(username, password, host, port, dbname)
            if session is None:
                Logger.log_error("Не удалось подключиться к базе данных")
                return False

            # Проверяем и устанавливаем расширение PostGIS при необходимости
            if not self.db_manager.ensure_postgis_extension(session):
                Logger.log_error("Расширение PostGIS недоступно. Работа с геометрией невозможна.")
                return False

            # Получаем имя файла из пути (оригинальное название)
            original_filename = os.path.basename(file_path)
            # Используем пользовательское название файла или оригинальное
            filename_for_db = custom_filename if custom_filename else original_filename

            Logger.log_message(f"Начало импорта DXF файла в базу данных...")
            Logger.log_message(f"Оригинальное название файла: {original_filename}")
            Logger.log_message(f"Название для БД: {filename_for_db}")
            Logger.log_message(f"Путь к файлу: {file_path}")
            Logger.log_message(f"Режим маппирования: {mapping_mode}")
            Logger.log_message(f"Схема для слоев: {layer_schema}")
            Logger.log_message(f"Схема для файлов: {file_schema}")
            Logger.log_message(f"Экспорт только слоев: {export_layers_only}")

            file_record = None

            # Создаем запись о файле только если не экспортируем только слои
            if not export_layers_only:
                # Читаем содержимое файла
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                # Создаем запись о файле в указанной схеме с названием для БД
                file_record = self.db_manager.create_file_record(session, filename_for_db, file_content, file_schema)
                if not file_record:
                    return False

            # Получаем слои DXF файла используя оригинальное название
            layers_entities = dxf_handler.get_entities_for_export(original_filename)

            # Для каждого слоя создаем таблицу и записываем сущности
            for layer_name, entities in layers_entities.items():
                Logger.log_message(f"Обработка слоя: {layer_name}")

                # Проверяем, нужно ли сопоставление столбцов для этого слоя
                mapping_check = self.db_manager.needs_column_mapping(session, layer_name, layer_schema)
                Logger.log_message(f"Проверка сопоставления для слоя {layer_name}: {mapping_check['reason']}")

                # Определяем конфигурацию сопоставления для этого слоя
                layer_mapping_config = None

                # Сначала проверяем специфичную конфигурацию для слоя
                if column_mapping_configs and layer_name in column_mapping_configs:
                    layer_mapping_config = column_mapping_configs[layer_name]
                    Logger.log_message(f"Найдена специфичная конфигурация сопоставления для слоя {layer_name}")
                # Затем проверяем глобальную конфигурацию
                elif column_mapping_configs and 'global_pattern' in column_mapping_configs:
                    layer_mapping_config = column_mapping_configs['global_pattern']
                    Logger.log_message(f"Используется глобальная конфигурация сопоставления для слоя {layer_name}")
                # Проверяем глобальную конфигурацию с другим ключом
                elif column_mapping_configs and 'global' in column_mapping_configs:
                    layer_mapping_config = column_mapping_configs['global']
                    Logger.log_message(f"Используется глобальная конфигурация (global) для слоя {layer_name}")

                # Создаем таблицу слоя если она не существует (только для стандартного случая)
                if not mapping_check['needs_mapping'] or not layer_mapping_config:
                    layer_class = self.db_manager.create_layer_table_if_not_exists(layer_name, layer_schema, file_schema)
                    if not layer_class:
                        Logger.log_error(f"Не удалось создать таблицу для слоя {layer_name}")
                        continue

                # Используем file_id только если файл был сохранен
                file_id = file_record.id if file_record else None

                # В зависимости от режима маппирования выбираем различную стратегию
                if mapping_mode == "always_overwrite":

                    # Если нужно сопоставление столбцов И есть конфигурация сопоставления
                    if mapping_check['needs_mapping'] and layer_mapping_config:
                        Logger.log_message(f"Применяем сопоставление столбцов для слоя {layer_name}")
                        Logger.log_message(f"Конфигурация сопоставления: {layer_mapping_config}")

                        # Конвертируем DXF сущности в PostGIS формат перед передачей в apply_column_mapping
                        postgis_entities = []
                        for entity in entities:
                            converter = DXFToPostGISConverter()
                            postgis_entity = converter.convert_entity_to_postgis(entity)
                            if postgis_entity:
                                postgis_entities.append(postgis_entity)

                        # Используем функцию применения сопоставления столбцов
                        success = self.db_manager.apply_column_mapping(session, layer_name, layer_mapping_config,
                                                 postgis_entities, layer_schema, file_id)
                        if not success:
                            Logger.log_warning(f"Не удалось применить сопоставление столбцов для слоя {layer_name}, используем стандартный способ")
                            # Удаляем существующие записи
                            if file_id:
                                session.query(layer_class).filter_by(file_id=file_id).delete()
                            else:
                                session.query(layer_class).delete()
                            session.commit()
                            self._convert_and_insert_entities(session, entities, layer_class, file_id)
                    else:
                        # Стандартный способ: удаляем существующие записи и добавляем новые
                        Logger.log_message(f"Используем стандартный способ импорта для слоя {layer_name}")
                        if file_id:
                            session.query(layer_class).filter_by(file_id=file_id).delete()
                        else:
                            # Если экспортируем только слои, удаляем все записи в таблице слоя
                            session.query(layer_class).delete()
                        session.commit()
                        Logger.log_message(f"Все существующие записи в слое {layer_name} удалены")

                        # Конвертируем и вставляем новые сущности
                        self._convert_and_insert_entities(session, entities, layer_class, file_id)

            # Генерируем превью файла только если файл был сохранен
            if file_record:
                self._create_output_dxf(file_path, filename_for_db, dxf_handler)
            return True

        except Exception as e:
            session.rollback()
            # Получаем имя файла для логирования ошибок
            error_filename = custom_filename if custom_filename else os.path.basename(file_path)
            Logger.log_error(f"Ошибка при импорте DXF файла {error_filename} в базу данных: {str(e)}")
            return False

    def _create_output_dxf(self, file_path : str, filename: str, dxf_handler: DXFHandler) -> None:
        """Создание SVG превью DXF файла"""
        doc = dxf_handler.simle_read_dxf_file(file_path)
        dxf_handler.save_svg_preview(doc, doc.modelspace(), filename)

    def _convert_and_insert_entities(self, session: Session, entities, layer_class, file_id: Optional[int]) -> bool:
        """
        Конвертирует DXF сущности в PostGIS формат и вставляет их в базу данных

        Args:
            session: Сессия базы данных
            entities: Список DXF сущностей для обработки
            layer_class: Класс модели таблицы слоя
            file_id: ID файла (может быть None если экспортируем только слои)

        Returns:
            True в случае успеха, иначе False
        """
        try:
            # Конвертируем все сущности в PostGIS формат
            postgis_entities = []
            for entity in entities:
                # Преобразуем DXF сущность в формат PostGIS
                converter = DXFToPostGISConverter()
                postgis_entity = converter.convert_entity_to_postgis(entity)

                if postgis_entity:
                    postgis_entities.append(postgis_entity)

            # Вставляем преобразованные сущности через DatabaseManager
            if postgis_entities:
                return self.db_manager.insert_converted_entities(session, postgis_entities, layer_class, file_id)
            else:
                Logger.log_message("Нет сущностей для вставки после конвертации")
                return True

        except Exception as e:
            Logger.log_error(f"Ошибка при конвертации и вставке сущностей: {str(e)}")
            return False

    def _apply_field_mapping(self, entity_data, mappings):
        """Применяет сопоставление полей к данным сущности"""
        mapped_data = {}

        for dxf_field, value in entity_data.items():
            # Если есть сопоставление, используем его
            if dxf_field in mappings:
                db_field = mappings[dxf_field]
                if db_field:  # Проверяем, что сопоставленное поле не пустое
                    mapped_data[db_field] = value
            else:
                # Иначе используем оригинальное название поля (только если такое поле не игнорируется)
                mapped_data[dxf_field] = value

        return mapped_data

    def create_import_thread(self, username, password, address, port, dbname, dxf_handler, file_path,
                            mapping_mode, layer_schema='layer_schema', file_schema='file_schema',
                            export_layers_only=False, custom_filename=None, column_mapping_configs=None):
        """
        Create and return an ImportThread for asynchronous import execution.

        Args:
            username: Database username
            password: Database password
            address: Database host
            port: Database port
            dbname: Database name
            dxf_handler: DXFHandler instance
            file_path: Path to DXF file
            mapping_mode: Column mapping mode
            layer_schema: Layer schema name
            file_schema: File schema name
            export_layers_only: Whether to export layers only
            custom_filename: Custom filename for DB
            column_mapping_configs: Column mapping configurations

        Returns:
            ImportThread instance configured for import
        """
        # Create a lambda function that captures all parameters and calls import_dxf_to_database
        import_function = lambda: self.import_dxf_to_database(
            username=username,
            password=password,
            host=address,
            port=port,
            dbname=dbname,
            dxf_handler=dxf_handler,
            file_path=file_path,
            mapping_mode=mapping_mode,
            layer_schema=layer_schema,
            file_schema=file_schema,
            export_layers_only=export_layers_only,
            custom_filename=custom_filename,
            column_mapping_configs=column_mapping_configs
        )

        return ImportThread(import_function)
