"""
DXF to Database Importer
Handles importing DXF files into PostGIS database.
"""

import os
from typing import Optional, Dict, List
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy import create_engine, text, inspect, MetaData, Table
from sqlalchemy.orm import sessionmaker, close_all_sessions
from datetime import datetime, timezone

from .converter import DXFToPostGISConverter
from ..db import models
from ..db.base import Base
from ..logger.logger import Logger
from ..dxf.dxf_handler import DXFHandler
from ..gui.column_mapping_dialog import ColumnMappingDialog


class DXFImporter:
    """
    Handles importing DXF files into PostGIS database.
    """

    # Constants
    DEFAULT_FILE_SCHEMA = 'file_schema'
    DEFAULT_LAYER_SCHEMA = 'layer_schema'
    DATABASE_URL_PATTERN = 'postgresql://{username}:{password}@{address}:{port}/{dbname}'
    CLIENT_ENCODING = 'WIN1251'

    # Class variables for database engine and session factory
    _engine = None
    _SessionLocal = None

    def __init__(self):
        self.logger = Logger

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
            db_url = DXFImporter.DATABASE_URL_PATTERN.format(
                username=username,
                password=password,
                address=host,
                port=port,
                dbname=dbname
            )

            DXFImporter._engine = create_engine(
                db_url,
                connect_args={
                    'client_encoding': DXFImporter.CLIENT_ENCODING,
                }
            )
            DXFImporter._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=DXFImporter._engine)

            session = DXFImporter._SessionLocal()

            # Проверяем и устанавливаем расширение PostGIS при необходимости
            if not self.ensure_postgis_extension(session):
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
                file_record = self.create_file_record(session, filename_for_db, file_content, file_schema)
                if not file_record:
                    return False

            # Получаем слои DXF файла используя оригинальное название
            layers_entities = dxf_handler.get_entities_for_export(original_filename)

            # Для каждого слоя создаем таблицу и записываем сущности
            for layer_name, entities in layers_entities.items():
                Logger.log_message(f"Обработка слоя: {layer_name}")

                # Проверяем, нужно ли сопоставление столбцов для этого слоя
                mapping_check = self.needs_column_mapping(session, layer_name, layer_schema)
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
                    layer_class = self.create_layer_table_if_not_exists(layer_name, layer_schema, file_schema)
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

                        # Используем функцию применения сопоставления столбцов
                        success = self.apply_column_mapping(session, layer_name, layer_mapping_config,
                                                 entities, layer_schema, file_id)
                        if not success:
                            Logger.log_warning(f"Не удалось применить сопоставление столбцов для слоя {layer_name}, используем стандартный способ")
                            # Удаляем существующие записи
                            if file_id:
                                session.query(layer_class).filter_by(file_id=file_id).delete()
                            else:
                                session.query(layer_class).delete()
                            session.commit()
                            self._add_new_entities(session, entities, layer_class, file_id)
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

                        # Добавляем новые сущности стандартным способом
                        self._add_new_entities(session, entities, layer_class, file_id)

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

    def ensure_postgis_extension(self, session: Session) -> bool:
        """
        Checks for PostGIS extension in the database and creates it if necessary.

        Args:
            session: Database session

        Returns:
            True if extension is available, False otherwise
        """
        try:
            with session.bind.connect() as connection:
                # Проверяем наличие расширения PostGIS
                result = connection.execute(text("""
                    SELECT EXISTS(
                        SELECT 1 FROM pg_extension WHERE extname = 'postgis'
                    );
                """))

                extension_exists = result.scalar()

                if not extension_exists:
                    Logger.log_message("Расширение PostGIS не найдено, пытаемся создать...")

                    # Пытаемся создать расширение PostGIS
                    try:
                        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                        connection.commit()
                        Logger.log_message("Расширение PostGIS успешно создано")
                        return True
                    except Exception as create_error:
                        Logger.log_error(f"Не удалось создать расширение PostGIS: {str(create_error)}")

                        # Проверяем, доступно ли расширение для установки
                        try:
                            available_result = connection.execute(text("""
                                SELECT EXISTS(
                                    SELECT 1 FROM pg_available_extensions WHERE name = 'postgis'
                                );
                            """))

                            if available_result.scalar():
                                Logger.log_error("Расширение PostGIS доступно, но не удалось его установить. Проверьте права доступа.")
                            else:
                                Logger.log_error("Расширение PostGIS недоступно на сервере PostgreSQL. Обратитесь к администратору.")
                        except Exception:
                            Logger.log_error("Не удалось проверить доступность расширения PostGIS")

                        return False
                else:
                    Logger.log_message("Расширение PostGIS уже установлено")
                    return True

        except Exception as e:
            Logger.log_error(f"Ошибка при проверке расширения PostGIS: {str(e)}")
            return False

    def create_file_record(self, session: Session, filename: str, file_content: bytes, file_schema: str = 'file_schema'):
        """
        Создает запись о DXF файле в базе данных

        Args:
            session: Сессия базы данных
            filename: Имя файла
            file_content: Содержимое файла в бинарном формате
            file_schema: Схема для размещения таблицы файлов

        Returns:
            Экземпляр модели DxfFile или None в случае ошибки
        """
        try:
            now = datetime.now(timezone.utc)

            # Создаем или получаем класс таблицы файлов для указанной схемы
            file_class = models.ModelFactory.create_file_table(file_schema)

            # Создаем таблицу, если она не существует
            file_class.__table__.create(DXFImporter._engine, checkfirst=True)

            # Проверяем, существует ли файл с таким именем
            existing_file = session.query(file_class).filter(file_class.filename == filename).first()

            if (existing_file):
                # Обновляем существующий файл
                existing_file.file_content = file_content
                existing_file.update_date = now
                session.commit()
                Logger.log_message(f"Файл {filename} обновлен в базе данных.")
                return existing_file
            else:
                # Создаем новую запись
                new_file = file_class(
                    filename=filename,
                    file_content=file_content,
                    upload_date=now,
                    update_date=now
                )
                session.add(new_file)
                session.commit()
                Logger.log_message(f"Файл {filename} добавлен в базу данных в схему {file_schema}.")
                return new_file
        except Exception as e:
            session.rollback()
            Logger.log_error(f"Ошибка при создании записи файла {filename}: {str(e)}")
            return None

    def create_layer_table_if_not_exists(self, layer_name: str, layer_schema: str = 'layer_schema', file_schema: str = 'file_schema') -> Optional[type]:
        """
        Создает таблицу для слоя, если она не существует

        Args:
            layer_name: Имя слоя
            layer_schema: Схема для размещения таблицы слоя
            file_schema: Схема где находится таблица файлов

        Returns:
            Класс таблицы для слоя или None в случае ошибки
        """
        try:
            # Нормализуем имя таблицы (заменяем пробелы и дефисы на подчеркивания)
            table_name = layer_name.replace(' ', '_').replace('-', '_')

            # Проверяем существование таблицы
            inspector = inspect(DXFImporter._engine)
            table_exists = inspector.has_table(table_name, schema=layer_schema)

            if not table_exists:
                # Создаем класс таблицы
                layer_class = models.ModelFactory.create_layer_table(layer_name, layer_schema, file_schema)
                # Создаем таблицу в базе данных
                layer_class.__table__.create(DXFImporter._engine, checkfirst=True)
                Logger.log_message(f"Создана таблица для слоя {layer_name} в схеме {layer_schema}")
                return layer_class
            else:
                # Возвращаем существующий класс таблицы
                return models.ModelFactory.create_layer_table(layer_name, layer_schema, file_schema)
        except Exception as e:
            Logger.log_error(f"Ошибка при создании таблицы для слоя {layer_name} в схеме {layer_schema}: {str(e)}")
            return None

    def _create_output_dxf(self, file_path : str, filename: str, dxf_handler: DXFHandler) -> None:
        """Создание SVG превью DXF файла"""
        doc = dxf_handler.simle_read_dxf_file(file_path)
        dxf_handler.save_svg_preview(doc, doc.modelspace(), filename)

    def _add_new_entities(self, session: Session, entities, layer_class, file_id: Optional[int]) -> None:
        """
        Добавляет новые сущности в таблицу слоя

        Args:
            session: Сессия базы данных
            entities: Список сущностей для добавления
            layer_class: Класс модели таблицы слоя
            file_id: ID файла (может быть None если экспортируем только слои)
        """
        try:
            for entity in entities:
                # Преобразуем DXF сущность в формат PostGIS
                converter = DXFToPostGISConverter()
                postgis_entity = converter.convert_entity_to_postgis(entity)

                if postgis_entity:
                    # Создаем новый экземпляр модели слоя
                    # Добавляем file_id только если он существует
                    layer_entity_data = {
                        'geom_type': postgis_entity['geom_type'],
                        'geometry': postgis_entity['geometry'],
                        'notes': postgis_entity.get('notes', None),
                        'extra_data': postgis_entity.get('extra_data', None)
                    }

                    if file_id is not None:
                        layer_entity_data['file_id'] = file_id

                    layer_entity = layer_class(**layer_entity_data)
                    session.add(layer_entity)

            # Сохраняем изменения в базе данных
            session.commit()
            Logger.log_message(f"Добавлено {len(entities)} новых сущностей в слой")
        except Exception as e:
            session.rollback()
            Logger.log_error(f"Ошибка при добавлении новых сущностей: {str(e)}")

    def apply_column_mapping(self, session, layer_name, mapping_config, entities, layer_schema='layer_schema', file_id=None):
        """
        Применяет настройки сопоставления столбцов при импорте сущностей

        Args:
            session: Сессия базы данных
            layer_name: Имя слоя
            mapping_config: Конфигурация сопоставления столбцов
            entities: Список сущностей для импорта
            layer_schema: Схема слоя
            file_id: ID файла (может быть None если импортируем только слои)

        Returns:
            True в случае успеха, иначе False
        """
        try:
            if not mapping_config:
                Logger.log_message("Настройки сопоставления столбцов не предоставлены")
                return False

            Logger.log_message(f"Применение сопоставления столбцов для слоя {layer_name}")
            Logger.log_message(f"Конфигурация: {mapping_config}")

            strategy = mapping_config.get('strategy', 'mapping_only')
            mappings = mapping_config.get('mappings', {})
            new_columns = mapping_config.get('new_columns', [])
            target_table = mapping_config.get('target_table')

            if not target_table:
                Logger.log_error("Целевая таблица не указана в настройках сопоставления")
                return False

            # Получаем класс существующей таблицы
            table_name = target_table.replace(' ', '_').replace('-', '_')

            # Создаем динамический класс для существующей таблицы
            # Отражаем существующую таблицу из базы данных
            metadata = MetaData()
            existing_table = Table(table_name, metadata, autoload_with=session.bind, schema=layer_schema)

            # Создаем динамический класс для работы с существующей таблицей
            layer_class = type(
                f"ExistingLayer_{table_name}",
                (Base,),
                {
                    '__table__': existing_table,
                    '__mapper_args__': {'primary_key': [existing_table.c.id] if 'id' in existing_table.c else []}
                }
            )

            # Если стратегия включает добавление столбцов
            if strategy in ['mapping_add_columns', 'mapping_add_backup']:
                self._add_columns_to_table(session, layer_class, new_columns)

                # После добавления столбцов обновляем метаданные таблицы
                metadata = MetaData()
                existing_table = Table(table_name, metadata, autoload_with=session.bind, schema=layer_schema)

                # Пересоздаем динамический класс с обновленной структурой таблицы
                layer_class = type(
                    f"ExistingLayer_{table_name}",
                    (Base,),
                    {
                        '__table__': existing_table,
                        '__mapper_args__': {'primary_key': [existing_table.c.id] if 'id' in existing_table.c else []}
                    }
                )

            # Если стратегия включает создание backup
            if strategy in ['mapping_backup', 'mapping_add_backup']:
                self._create_backup_table(session, layer_class, layer_name, layer_schema)

            # Очищаем существующие записи для этого файла, если file_id указан
            if file_id is not None:
                # Используем сопоставленное имя столбца для file_id
                file_id_column = mappings.get('file_id', 'file_id')
                if hasattr(existing_table.c, file_id_column):
                    delete_query = session.query(layer_class).filter(getattr(existing_table.c, file_id_column) == file_id)
                    deleted_count = delete_query.count()
                    delete_query.delete()
                    Logger.log_message(f"Удалено {deleted_count} существующих записей для {file_id_column}={file_id}")
                else:
                    Logger.log_warning(f"Столбец {file_id_column} не найден в таблице, пропускаем очистку записей")
            else:
                # Если file_id не указан, очищаем всю таблицу
                deleted_count = session.query(layer_class).count()
                session.query(layer_class).delete()
                Logger.log_message(f"Удалено {deleted_count} записей из таблицы {table_name}")

            session.commit()

            # Применяем сопоставление к каждой сущности
            added_count = 0
            for entity in entities:
                try:
                    # Конвертируем сущность в PostGIS формат
                    converter = DXFToPostGISConverter()
                    postgis_data = converter.convert_entity_to_postgis(entity)

                    if not postgis_data:
                        Logger.log_warning(f"Не удалось преобразовать сущность {entity}")
                        continue

                    # Применяем сопоставление полей
                    mapped_data = self._apply_field_mapping(postgis_data, mappings)

                    # Добавляем file_id если предоставлен, используя сопоставленное имя столбца
                    if file_id is not None:
                        file_id_column = mappings.get('file_id', 'file_id')
                        mapped_data[file_id_column] = file_id

                    # Фильтруем данные, оставляя только те поля, которые существуют в целевой таблице
                    filtered_data = {}
                    for field_name, field_value in mapped_data.items():
                        if hasattr(existing_table.c, field_name):
                            filtered_data[field_name] = field_value
                        else:
                            Logger.log_warning(f"Поле {field_name} не существует в целевой таблице, пропускаем")

                    # Создаем новую запись в таблице
                    layer_record = layer_class(**filtered_data)
                    session.add(layer_record)
                    added_count += 1

                except Exception as e:
                    Logger.log_error(f"Ошибка при обработке сущности: {str(e)}")
                    continue

            session.commit()
            Logger.log_message(f"Успешно применено сопоставление столбцов: добавлено {added_count} из {len(entities)} сущностей")
            return True

        except Exception as e:
            session.rollback()
            Logger.log_error(f"Ошибка при применении сопоставления столбцов для слоя {layer_name}: {str(e)}")
            return False

    def _add_columns_to_table(self, session, table_class, columns):
        """Добавляет новые столбцы в существующую таблицу"""
        try:
            # Получаем имя таблицы и схему из объекта Table
            table_obj = table_class.__table__
            table_name = table_obj.name
            schema_name = table_obj.schema

            # Маппинг типов столбцов на основе DxfLayerBase из models.py
            column_types_mapping = {
                'id': 'INTEGER PRIMARY KEY',
                'file_id': 'INTEGER',
                'geometry': 'GEOMETRY(GEOMETRYZ, 4326)',
                'geom_type': 'VARCHAR',
                'notes': 'TEXT',
                'extra_data': 'JSONB'
            }

            for column_name in columns:
                # Определяем тип столбца на основе маппинга
                column_type = column_types_mapping.get(column_name, "TEXT")

                alter_sql = text(f"""
                    ALTER TABLE "{schema_name}"."{table_name}"
                    ADD COLUMN IF NOT EXISTS "{column_name}" {column_type}
                """)

                session.execute(alter_sql)
                Logger.log_message(f"Добавлен столбец {column_name} ({column_type}) в таблицу {schema_name}.{table_name}")

            session.commit()

        except Exception as e:
            session.rollback()
            Logger.log_error(f"Ошибка при добавлении столбцов: {str(e)}")

    def _create_backup_table(self, session, table_class, layer_name, layer_schema):
        """Создает backup таблицу с оригинальной структурой"""
        try:
            from datetime import datetime

            # Получаем имя таблицы из объекта Table
            table_obj = table_class.__table__
            original_table = table_obj.name
            backup_table = f"{original_table}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            backup_sql = text(f"""
                CREATE TABLE "{layer_schema}"."{backup_table}" AS
                SELECT * FROM "{layer_schema}"."{original_table}"
            """)

            session.execute(backup_sql)
            session.commit()

            Logger.log_message(f"Создана backup таблица: {layer_schema}.{backup_table}")

        except Exception as e:
            session.rollback()
            Logger.log_error(f"Ошибка при создании backup таблицы: {str(e)}")

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

    def needs_column_mapping(self, session, layer_name, layer_schema='layer_schema'):
        """
        Проверяет, нужно ли сопоставление столбцов для данного слоя

        Args:
            session: Сессия базы данных
            layer_name: Имя слоя
            layer_schema: Схема слоя

        Returns:
            dict: {'needs_mapping': bool, 'existing_columns': list, 'reason': str}
        """
        try:
            # Нормализуем имя таблицы
            table_name = layer_name.replace(' ', '_').replace('-', '_')

            # Проверяем существование таблицы используя существующую сессию
            inspector = inspect(session.bind)
            table_exists_flag = inspector.has_table(table_name, schema=layer_schema)

            if not table_exists_flag:
                return {
                    'needs_mapping': False,
                    'existing_columns': [],
                    'reason': 'Таблица не существует, будет создана новая'
                }

            # Получаем столбцы существующей таблицы используя существующую сессию
            with session.bind.connect() as connection:
                result = connection.execute(text("""
                    SELECT
                        column_name,
                        data_type,
                        is_nullable,
                        column_default,
                        character_maximum_length
                    FROM information_schema.columns
                    WHERE table_schema = :schema_name
                    AND table_name = :table_name
                    ORDER BY ordinal_position
                """), {'schema_name': layer_schema, 'table_name': table_name})

                existing_columns = []
                for row in result:
                    existing_columns.append({
                        'name': row[0],
                        'type': row[1],
                        'nullable': row[2] == 'YES',
                        'default': row[3],
                        'max_length': row[4]
                    })

            # Стандартные столбцы DXF таблицы
            standard_dxf_columns = ['id', 'file_id', 'geometry', 'geom_type', 'notes', 'extra_data']

            # Проверяем, есть ли различия в структуре
            existing_column_names = [col['name'] for col in existing_columns]

            # Если в существующей таблице отсутствуют стандартные столбцы DXF
            missing_standard_columns = [col for col in standard_dxf_columns if col not in existing_column_names]

            # Если в существующей таблице есть дополнительные столбцы, не являющиеся стандартными DXF
            extra_columns = [col for col in existing_column_names if col not in standard_dxf_columns]

            if missing_standard_columns or extra_columns:
                reason = []
                if missing_standard_columns:
                    reason.append(f"Отсутствуют стандартные DXF столбцы: {', '.join(missing_standard_columns)}")
                if extra_columns:
                    reason.append(f"Дополнительные столбцы в существующей таблице: {', '.join(extra_columns)}")

                return {
                    'needs_mapping': True,
                    'existing_columns': existing_columns,
                    'reason': '; '.join(reason)
                }

            return {
                'needs_mapping': False,
                'existing_columns': existing_columns,
                'reason': 'Структура таблицы соответствует стандартной DXF структуре'
            }

        except Exception as e:
            Logger.log_error(f"Ошибка при проверке необходимости сопоставления столбцов: {str(e)}")
            return {
                'needs_mapping': False,
                'existing_columns': [],
                'reason': f'Ошибка проверки: {str(e)}'
            }
