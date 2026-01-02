# -*- coding: utf-8 -*-
"""
DXF Repository - единый репозиторий для работы с DXF файлами и слоями.

Объединяет:
- CRUD операции для файлов
- CRUD операции для слоёв
- Работу со схемами

НЕ содержит UI-логики!
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text, inspect, MetaData, Table
from sqlalchemy.orm import Session

from .connection import DatabaseConnection
from ...application.settings_service import ConnectionSettings
from . import models
from .base import Base
from ...logger.logger import Logger


@dataclass
class DxfFileInfo:
    """Информация о DXF файле."""
    id: int
    filename: str
    upload_date: Optional[datetime]
    update_date: Optional[datetime]


@dataclass
class ColumnInfo:
    """Информация о столбце таблицы."""
    name: str
    data_type: str
    nullable: bool
    default: Optional[str] = None
    max_length: Optional[int] = None


@dataclass
class ColumnMappingCheck:
    """Результат проверки необходимости маппинга столбцов."""
    needs_mapping: bool
    existing_columns: List[ColumnInfo]
    reason: str


class DxfRepository:
    """
    Единый репозиторий для работы с DXF файлами и слоями.
    
    Все операции с базой данных проходят через этот класс.
    Не содержит UI-логики и не показывает диалогов!
    """
    
    def __init__(self, connection: Optional[DatabaseConnection] = None):
        """
        Args:
            connection: Подключение к БД. Если None, используется singleton.
        """
        self._connection = connection or DatabaseConnection.instance()
    
    # ========== Операции со схемами ==========
    
    def get_schemas(self, session: Session) -> List[str]:
        """
        Получить список всех схем в базе данных.
        
        Args:
            session: Активная сессия БД
            
        Returns:
            Список названий схем
        """
        try:
            result = session.execute(text("""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name NOT IN (
                    'information_schema', 'pg_catalog', 'pg_toast', 
                    'pg_temp_1', 'pg_toast_temp_1'
                )
                ORDER BY schema_name;
            """))
            schemas = [row[0] for row in result]
            Logger.log_message(f"Найдено схем: {len(schemas)}")
            return schemas
        except Exception as e:
            Logger.log_error(f"Ошибка получения схем: {str(e)}")
            return []
    
    def create_schema(self, session: Session, schema_name: str) -> bool:
        """
        Создать новую схему в базе данных.
        
        Args:
            session: Активная сессия БД
            schema_name: Название схемы
            
        Returns:
            True если успешно
        """
        try:
            # Проверяем существование
            result = session.execute(text("""
                SELECT 1 FROM information_schema.schemata
                WHERE schema_name = :schema_name
            """), {"schema_name": schema_name})
            
            if result.fetchone():
                Logger.log_message(f"Схема '{schema_name}' уже существует")
                return True
            
            # Создаём схему
            session.execute(text(f'CREATE SCHEMA "{schema_name}";'))
            session.commit()
            Logger.log_message(f"Схема '{schema_name}' создана")
            return True
                
        except Exception as e:
            Logger.log_error(f"Ошибка создания схемы '{schema_name}': {str(e)}")
            return False
    
    def schema_exists(self, session: Session, schema_name: str) -> bool:
        """Проверить существование схемы."""
        try:
            result = session.execute(text("""
                SELECT 1 FROM information_schema.schemata
                WHERE schema_name = :schema_name
            """), {"schema_name": schema_name})
            return result.fetchone() is not None
        except Exception as e:
            Logger.log_error(f"Ошибка проверки схемы: {str(e)}")
            return False
    
    # ========== Операции с файлами ==========
    
    def ensure_file_table(
        self, 
        session: Session, 
        schema: str = 'file_schema'
    ) -> bool:
        """
        Убедиться что таблица dxf_files существует.
        
        Args:
            session: Активная сессия БД
            schema: Схема для размещения
            
        Returns:
            True если таблица существует или была создана
        """
        try:
            file_class = models.ModelFactory.create_file_table(schema)
            engine = self._connection.get_engine()
            if engine:
                file_class.__table__.create(engine, checkfirst=True)
                Logger.log_message(f"Таблица dxf_files проверена/создана в схеме '{schema}'")
                return True
            return False
        except Exception as e:
            Logger.log_error(f"Ошибка создания таблицы dxf_files в схеме '{schema}': {str(e)}")
            return False
    
    def create_file(
        self, 
        session: Session, 
        filename: str, 
        content: bytes, 
        schema: str = 'file_schema'
    ) -> Optional[Any]:
        """
        Создать или обновить запись о DXF файле.
        
        Args:
            session: Активная сессия БД
            filename: Имя файла
            content: Содержимое файла
            schema: Схема для размещения
            
        Returns:
            Экземпляр модели файла или None
        """
        try:
            now = datetime.now(timezone.utc)
            file_class = models.ModelFactory.create_file_table(schema)
            
            # Создаём таблицу если не существует
            engine = self._connection.get_engine()
            if engine:
                file_class.__table__.create(engine, checkfirst=True)
            
            # Проверяем существование файла
            existing = session.query(file_class).filter(
                file_class.filename == filename
            ).first()
            
            if existing:
                existing.file_content = content
                existing.update_date = now
                session.commit()
                Logger.log_message(f"Файл '{filename}' обновлён в схеме '{schema}'")
                return existing
            else:
                new_file = file_class(
                    filename=filename,
                    file_content=content,
                    upload_date=now,
                    update_date=now
                )
                session.add(new_file)
                session.commit()
                Logger.log_message(f"Файл '{filename}' создан в схеме '{schema}'")
                return new_file
                
        except Exception as e:
            session.rollback()
            Logger.log_error(f"Ошибка создания файла '{filename}': {str(e)}")
            return None
    
    def get_file_by_id(
        self, 
        session: Session, 
        file_id: int, 
        schema: str = 'file_schema'
    ) -> Optional[Any]:
        """Получить файл по ID."""
        try:
            file_class = models.ModelFactory.create_file_table(schema)
            return session.query(file_class).filter(file_class.id == file_id).first()
        except Exception as e:
            Logger.log_error(f"Ошибка получения файла ID={file_id}: {str(e)}")
            return None
    
    def get_all_files(
        self, 
        session: Session, 
        schema: str = 'file_schema'
    ) -> List[DxfFileInfo]:
        """
        Получить список всех DXF файлов.
        
        Args:
            session: Активная сессия БД
            schema: Схема для поиска
            
        Returns:
            Список информации о файлах
        """
        try:
            file_class = models.ModelFactory.create_file_table(schema)
            files = session.query(file_class).all()
            
            return [
                DxfFileInfo(
                    id=f.id,
                    filename=f.filename,
                    upload_date=f.upload_date,
                    update_date=f.update_date
                )
                for f in files
            ]
        except Exception as e:
            Logger.log_error(f"Ошибка получения файлов из схемы '{schema}': {str(e)}")
            return []
    
    def delete_file(
        self, 
        session: Session, 
        file_id: int, 
        schema: str = 'file_schema'
    ) -> bool:
        """Удалить файл по ID."""
        try:
            file_class = models.ModelFactory.create_file_table(schema)
            file_record = session.query(file_class).filter(
                file_class.id == file_id
            ).first()
            
            if not file_record:
                Logger.log_warning(f"Файл ID={file_id} не найден")
                return False
            
            filename = file_record.filename
            session.delete(file_record)
            session.commit()
            Logger.log_message(f"Файл '{filename}' удалён")
            return True
            
        except Exception as e:
            session.rollback()
            Logger.log_error(f"Ошибка удаления файла ID={file_id}: {str(e)}")
            return False
    
    def get_file_content(
        self, 
        session: Session, 
        file_id: int, 
        schema: str = 'file_schema'
    ) -> Optional[bytes]:
        """Получить содержимое файла."""
        file_record = self.get_file_by_id(session, file_id, schema)
        return file_record.file_content if file_record else None
    
    # ========== Операции со слоями ==========
    
    def create_layer_table(
        self, 
        session: Session, 
        layer_name: str, 
        layer_schema: str = 'layer_schema',
        file_schema: str = 'file_schema'
    ) -> Optional[type]:
        """
        Создать таблицу для слоя если не существует.
        
        Args:
            session: Активная сессия БД
            layer_name: Имя слоя
            layer_schema: Схема для таблицы слоя
            file_schema: Схема с таблицей файлов
            
        Returns:
            Класс таблицы или None
        """
        try:
            table_name = layer_name.replace(' ', '_').replace('-', '_')
            engine = self._connection.get_engine()
            
            if not engine:
                return None
            
            inspector = inspect(engine)
            table_exists = inspector.has_table(table_name, schema=layer_schema)
            
            layer_class = models.ModelFactory.create_layer_table(
                layer_name, layer_schema, file_schema
            )
            
            if not table_exists:
                layer_class.__table__.create(engine, checkfirst=True)
                Logger.log_message(
                    f"Таблица слоя '{layer_name}' создана в схеме '{layer_schema}'"
                )
            
            return layer_class
            
        except Exception as e:
            Logger.log_error(f"Ошибка создания таблицы слоя '{layer_name}': {str(e)}")
            return None
    
    def insert_entities(
        self,
        session: Session,
        layer_class: type,
        entities: List[Dict[str, Any]],
        file_id: Optional[int] = None
    ) -> bool:
        """
        Вставить сущности в таблицу слоя.
        
        Args:
            session: Активная сессия БД
            layer_class: Класс модели слоя
            entities: Список сущностей в формате PostGIS
            file_id: ID файла (опционально)
            
        Returns:
            True если успешно
        """
        try:
            for entity in entities:
                entity_data = {
                    'geom_type': entity['geom_type'],
                    'geometry': entity['geometry'],
                    'notes': entity.get('notes'),
                    'extra_data': entity.get('extra_data'),
                }
                
                if file_id is not None:
                    entity_data['file_id'] = file_id
                
                layer_entity = layer_class(**entity_data)
                session.add(layer_entity)
            
            session.commit()
            Logger.log_message(f"Добавлено {len(entities)} сущностей")
            return True
            
        except Exception as e:
            session.rollback()
            Logger.log_error(f"Ошибка вставки сущностей: {str(e)}")
            return False
    
    def clear_layer(
        self,
        session: Session,
        layer_class: type,
        file_id: Optional[int] = None
    ) -> bool:
        """
        Очистить таблицу слоя.
        
        Args:
            session: Активная сессия БД
            layer_class: Класс модели слоя
            file_id: Если указан, удаляются только записи с этим file_id
            
        Returns:
            True если успешно
        """
        try:
            if file_id is not None:
                session.query(layer_class).filter_by(file_id=file_id).delete()
            else:
                session.query(layer_class).delete()
            
            session.commit()
            Logger.log_message("Слой очищен")
            return True
            
        except Exception as e:
            session.rollback()
            Logger.log_error(f"Ошибка очистки слоя: {str(e)}")
            return False
    
    def get_table_columns(
        self, 
        session: Session, 
        table_name: str, 
        schema: str = 'public'
    ) -> List[ColumnInfo]:
        """Получить информацию о столбцах таблицы."""
        try:
            result = session.execute(text("""
                SELECT
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = :schema
                AND table_name = :table_name
                ORDER BY ordinal_position
            """), {'schema': schema, 'table_name': table_name})
            
            return [
                ColumnInfo(
                    name=row[0],
                    data_type=row[1],
                    nullable=row[2] == 'YES',
                    default=row[3],
                    max_length=row[4]
                )
                for row in result
            ]
                
        except Exception as e:
            Logger.log_error(f"Ошибка получения столбцов: {str(e)}")
            return []
    
    def table_exists(
        self, 
        session: Session, 
        table_name: str, 
        schema: str = 'public'
    ) -> bool:
        """Проверить существование таблицы."""
        try:
            result = session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = :schema
                    AND table_name = :table_name
                )
            """), {'schema': schema, 'table_name': table_name})
            return result.scalar()
        except Exception as e:
            Logger.log_error(f"Ошибка проверки таблицы: {str(e)}")
            return False
    
    # ========== Поиск по схемам ==========
    
    def find_files_in_schemas(
        self, 
        session: Session, 
        schemas_to_try: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Найти файлы, пробуя разные схемы.
        
        НЕ показывает UI-диалогов! Возвращает результат для обработки
        на уровне Application.
        
        Args:
            session: Активная сессия БД
            schemas_to_try: Список схем для проверки
            
        Returns:
            {'files': List[DxfFileInfo], 'schema': str} или 
            {'files': [], 'schema': None, 'available_schemas': List[str]}
        """
        if schemas_to_try is None:
            schemas_to_try = ['file_schema', 'public']
        
        available_schemas = self.get_schemas(session)
        
        for schema in schemas_to_try:
            if schema not in available_schemas:
                continue
                
            files = self.get_all_files(session, schema)
            if files:
                return {'files': files, 'schema': schema}
        
        # Ничего не найдено — возвращаем доступные схемы для выбора
        return {
            'files': [],
            'schema': None,
            'available_schemas': available_schemas
        }
    
    def get_tables_in_schema(
        self, 
        session: Session, 
        schema: str = 'public'
    ) -> List[str]:
        """
        Получить список всех таблиц в схеме.
        
        Args:
            session: Активная сессия БД
            schema: Имя схемы
            
        Returns:
            Список имён таблиц
        """
        try:
            result = session.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = :schema_name
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """), {'schema_name': schema})
            
            tables = [row[0] for row in result]
            Logger.log_message(
                f"Найдено таблиц в схеме '{schema}': {len(tables)}"
            )
            return tables
                
        except Exception as e:
            Logger.log_error(
                f"Ошибка получения таблиц в схеме '{schema}': {str(e)}"
            )
            return []
    
    # ========== Column Mapping ==========
    
    def needs_column_mapping(
        self, 
        session: Session, 
        layer_name: str, 
        layer_schema: str = 'layer_schema'
    ) -> ColumnMappingCheck:
        """
        Проверить необходимость сопоставления столбцов для слоя.
        
        Args:
            session: Активная сессия БД
            layer_name: Имя слоя
            layer_schema: Схема слоя
            
        Returns:
            ColumnMappingCheck с результатом проверки
        """
        try:
            table_name = layer_name.replace(' ', '_').replace('-', '_')
            
            # Проверяем существование таблицы
            if not self.table_exists(session, table_name, layer_schema):
                return ColumnMappingCheck(
                    needs_mapping=False,
                    existing_columns=[],
                    reason='Таблица не существует, будет создана новая'
                )
            
            # Получаем столбцы
            existing_columns = self.get_table_columns(
                session, table_name, layer_schema
            )
            existing_column_names = [col.name for col in existing_columns]
            
            # Стандартные столбцы DXF
            standard_columns = ['id', 'file_id', 'geometry', 'geom_type', 'notes', 'extra_data']
            
            missing = [c for c in standard_columns if c not in existing_column_names]
            extra = [c for c in existing_column_names if c not in standard_columns]
            
            if missing or extra:
                reasons = []
                if missing:
                    reasons.append(f"Отсутствуют столбцы: {', '.join(missing)}")
                if extra:
                    reasons.append(f"Дополнительные столбцы: {', '.join(extra)}")
                
                return ColumnMappingCheck(
                    needs_mapping=True,
                    existing_columns=existing_columns,
                    reason='; '.join(reasons)
                )
            
            return ColumnMappingCheck(
                needs_mapping=False,
                existing_columns=existing_columns,
                reason='Структура соответствует стандартной DXF'
            )
            
        except Exception as e:
            Logger.log_error(f"Ошибка проверки маппинга: {str(e)}")
            return ColumnMappingCheck(
                needs_mapping=False,
                existing_columns=[],
                reason=f'Ошибка: {str(e)}'
            )
    
    def apply_column_mapping(
        self,
        session: Session,
        layer_name: str,
        mapping_config: Dict[str, Any],
        postgis_entities: List[Dict[str, Any]],
        layer_schema: str = 'layer_schema',
        file_id: Optional[int] = None
    ) -> bool:
        """
        Применить сопоставление столбцов к PostGIS сущностям.
        
        Args:
            session: Активная сессия БД
            layer_name: Имя слоя
            mapping_config: Конфигурация сопоставления:
                - strategy: 'mapping_only' | 'mapping_add_columns' | 
                           'mapping_backup' | 'mapping_add_backup'
                - mappings: Dict[str, str] (DXF field → DB field)
                - new_columns: List[str]
                - target_table: str
            postgis_entities: Сущности для вставки
            layer_schema: Схема слоя
            file_id: ID файла (опционально)
            
        Returns:
            True при успехе
        """
        try:
            if not mapping_config:
                Logger.log_warning("Конфигурация маппинга не предоставлена")
                return False
            
            strategy = mapping_config.get('strategy', 'mapping_only')
            mappings = mapping_config.get('mappings', {})
            new_columns = mapping_config.get('new_columns', [])
            target_table = mapping_config.get('target_table')
            
            if not target_table:
                Logger.log_error("Целевая таблица не указана")
                return False
            
            table_name = target_table.replace(' ', '_').replace('-', '_')
            
            # Отражаем существующую таблицу
            metadata = MetaData()
            existing_table = Table(
                table_name, metadata, 
                autoload_with=session.bind, 
                schema=layer_schema
            )
            
            # Создаём динамический класс
            layer_class = type(
                f"ExistingLayer_{table_name}",
                (Base,),
                {
                    '__table__': existing_table,
                    '__mapper_args__': {
                        'primary_key': [existing_table.c.id] 
                        if 'id' in existing_table.c else []
                    }
                }
            )
            
            # Добавляем столбцы при необходимости
            if strategy in ['mapping_add_columns', 'mapping_add_backup']:
                self.add_columns_to_table(
                    session, table_name, layer_schema, new_columns
                )
                # Перезагружаем таблицу
                metadata = MetaData()
                existing_table = Table(
                    table_name, metadata,
                    autoload_with=session.bind,
                    schema=layer_schema
                )
                layer_class = type(
                    f"ExistingLayer_{table_name}",
                    (Base,),
                    {
                        '__table__': existing_table,
                        '__mapper_args__': {
                            'primary_key': [existing_table.c.id]
                            if 'id' in existing_table.c else []
                        }
                    }
                )
            
            # Создаём backup при необходимости
            if strategy in ['mapping_backup', 'mapping_add_backup']:
                self.create_backup_table(session, table_name, layer_schema)
            
            # Очищаем существующие записи
            if file_id is not None:
                file_id_column = mappings.get('file_id', 'file_id')
                if hasattr(existing_table.c, file_id_column):
                    delete_query = session.query(layer_class).filter(
                        getattr(existing_table.c, file_id_column) == file_id
                    )
                    deleted = delete_query.count()
                    delete_query.delete()
                    Logger.log_message(f"Удалено {deleted} записей")
            else:
                deleted = session.query(layer_class).count()
                session.query(layer_class).delete()
                Logger.log_message(f"Очищено {deleted} записей")
            
            session.commit()
            
            # Вставляем сущности с маппингом
            added = 0
            for entity in postgis_entities:
                if not entity:
                    continue
                
                mapped_data = self._apply_field_mapping(entity, mappings)
                
                if file_id is not None:
                    file_id_column = mappings.get('file_id', 'file_id')
                    mapped_data[file_id_column] = file_id
                
                # Фильтруем по существующим столбцам
                filtered_data = {
                    k: v for k, v in mapped_data.items()
                    if hasattr(existing_table.c, k)
                }
                
                session.add(layer_class(**filtered_data))
                added += 1
            
            session.commit()
            Logger.log_message(
                f"Применён маппинг: добавлено {added}/{len(postgis_entities)}"
            )
            return True
            
        except Exception as e:
            session.rollback()
            Logger.log_error(f"Ошибка применения маппинга: {str(e)}")
            return False
    
    def _apply_field_mapping(
        self, 
        entity_data: Dict[str, Any], 
        mappings: Dict[str, str]
    ) -> Dict[str, Any]:
        """Применить маппинг полей к данным сущности."""
        mapped = {}
        for field, value in entity_data.items():
            if field in mappings:
                db_field = mappings[field]
                if db_field:  # Не пустое значение
                    mapped[db_field] = value
            else:
                mapped[field] = value
        return mapped
    
    def add_columns_to_table(
        self,
        session: Session,
        table_name: str,
        schema: str,
        columns: List[str]
    ) -> bool:
        """
        Добавить новые столбцы в существующую таблицу.
        
        Args:
            session: Активная сессия БД
            table_name: Имя таблицы
            schema: Схема таблицы
            columns: Список имён столбцов для добавления
            
        Returns:
            True при успехе
        """
        try:
            # Маппинг типов по умолчанию
            type_mapping = {
                'id': 'INTEGER PRIMARY KEY',
                'file_id': 'INTEGER',
                'geometry': 'GEOMETRY(GEOMETRYZ, 4326)',
                'geom_type': 'VARCHAR',
                'notes': 'TEXT',
                'extra_data': 'JSONB'
            }
            
            for column_name in columns:
                column_type = type_mapping.get(column_name, 'TEXT')
                
                session.execute(text(f"""
                    ALTER TABLE "{schema}"."{table_name}"
                    ADD COLUMN IF NOT EXISTS "{column_name}" {column_type}
                """))
                Logger.log_message(
                    f"Добавлен столбец {column_name} ({column_type}) "
                    f"в таблицу {schema}.{table_name}"
                )
            
            session.commit()
            return True
            
        except Exception as e:
            session.rollback()
            Logger.log_error(f"Ошибка добавления столбцов: {str(e)}")
            return False
    
    def create_backup_table(
        self,
        session: Session,
        table_name: str,
        schema: str
    ) -> Optional[str]:
        """
        Создать backup копию таблицы.
        
        Args:
            session: Активная сессия БД
            table_name: Имя таблицы
            schema: Схема таблицы
            
        Returns:
            Имя созданной backup таблицы или None
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{table_name}_backup_{timestamp}"
            
            session.execute(text(f"""
                CREATE TABLE "{schema}"."{backup_name}" AS
                SELECT * FROM "{schema}"."{table_name}"
            """))
            session.commit()
            
            Logger.log_message(f"Создан backup: {schema}.{backup_name}")
            return backup_name
            
        except Exception as e:
            session.rollback()
            Logger.log_error(f"Ошибка создания backup: {str(e)}")
            return None

