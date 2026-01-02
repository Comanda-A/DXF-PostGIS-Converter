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

from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from .connection import DatabaseConnection
from ...application.settings_service import ConnectionSettings
from ...db import models
from ...db.base import Base
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
            with session.bind.connect() as conn:
                result = conn.execute(text("""
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
            with session.bind.connect() as conn:
                # Проверяем существование
                result = conn.execute(text("""
                    SELECT 1 FROM information_schema.schemata
                    WHERE schema_name = :schema_name
                """), {"schema_name": schema_name})
                
                if result.fetchone():
                    Logger.log_message(f"Схема '{schema_name}' уже существует")
                    return True
                
                # Создаём схему
                conn.execute(text(f'CREATE SCHEMA "{schema_name}";'))
                conn.commit()
                Logger.log_message(f"Схема '{schema_name}' создана")
                return True
                
        except Exception as e:
            Logger.log_error(f"Ошибка создания схемы '{schema_name}': {str(e)}")
            return False
    
    def schema_exists(self, session: Session, schema_name: str) -> bool:
        """Проверить существование схемы."""
        try:
            with session.bind.connect() as conn:
                result = conn.execute(text("""
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
            with session.bind.connect() as conn:
                result = conn.execute(text("""
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
            with session.bind.connect() as conn:
                result = conn.execute(text("""
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
