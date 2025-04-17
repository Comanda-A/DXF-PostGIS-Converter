from typing import List, Optional
from sqlalchemy.orm import declarative_base

from .converter_dxf_to_postgis import convert_entity_to_postgis

Base = declarative_base()

from sqlalchemy import create_engine, Engine, text, inspect, MetaData, select
from sqlalchemy.orm import sessionmaker, Session, close_all_sessions
from geoalchemy2.shape import  to_shape
from ..logger.logger import Logger
from datetime import datetime, timezone
from . import models
from ..dxf.dxf_handler import DXFHandler
import os

# Шаблон URL для подключения к базе данных
PATTERN_DATABASE_URL = 'postgresql://{username}:{password}@{address}:{port}/{dbname}'

# Глобальные переменные для хранения текущего движка, сессии и кэша файлов
engine = None
SessionLocal = None
_files_cache: dict = {}  # Кэш файлов


# ----------------------
# Основные функции работы с базой данных
# ----------------------

def _connect_to_database(username, password, address, port, dbname) -> Session:
    """Создание подключения к базе данных"""
    try:
        global engine, SessionLocal, _files_cache
        # Закрываем текущие сессии, если они есть
        if 'SessionLocal' in globals() and SessionLocal is not None:
            close_all_sessions()

        # Формируем URL базы данных
        db_url = PATTERN_DATABASE_URL.format(
            username=username, 
            password=password,
            address=address, 
            port=port, 
            dbname=dbname
        )

        # Создаем новый движок и сессию с правильными настройками кодировки
        engine = create_engine(
            db_url,
            connect_args={
                'client_encoding': 'WIN1251',  # более компактное хранение кириллицы
            }
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # Создаем схемы если их нет
        _create_schemas()
        
        # Создаем все таблицы, если их нет
        Base.metadata.create_all(bind=engine)

        # Логируем успешное подключение
        Logger.log_message(f"Подключено к базе данных PostgreSQL '{dbname}' по адресу {address}:{port} с пользователем '{username}'.")

        session = SessionLocal()
        
        return session
    except Exception as e:
        Logger.log_error(f"Ошибка подключения к базе данных PostgreSQL '{dbname}' по адресу {address}:{port} с пользователем '{username}': {str(e)}")
        return None

def _create_schemas():
    """Создание необходимых схем в базе данных"""
    try:
        with engine.connect() as connection:
            # Проверяем и создаем расширение PostGIS
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS file_schema;"))
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS layer_schema;"))
            connection.commit()
        Logger.log_message("Схемы и расширение PostGIS успешно созданы или уже существуют.")
    except Exception as e:
        Logger.log_error(f"Ошибка при создании схем: {str(e)}")

def get_session() -> Session:
    """Получение сессии базы данных"""
    global SessionLocal
    if SessionLocal is None:
        raise Exception("База данных не подключена. Вызовите _connect_to_database сначала.")
    return SessionLocal()


# ----------------------
# Методы создания сущностей
# ----------------------

def create_file_record(session: Session, filename: str, file_content: bytes) -> Optional[models.DxfFile]:
    """
    Создает запись о DXF файле в базе данных
    
    Args:
        session: Сессия базы данных
        filename: Имя файла
        file_content: Содержимое файла в бинарном формате

    Returns:
        Экземпляр модели DxfFile или None в случае ошибки
    """
    try:
        now = datetime.now(timezone.utc)
        
        # Проверяем, существует ли файл с таким именем
        existing_file = session.query(models.DxfFile).filter_by(filename=filename).first()
        
        if (existing_file):
            # Обновляем существующий файл
            existing_file.file_content = file_content
            existing_file.update_date = now
            session.commit()
            Logger.log_message(f"Файл {filename} обновлен в базе данных.")
            return existing_file
        else:
            # Создаем новую запись
            new_file = models.DxfFile(
                filename=filename,
                file_content=file_content,
                upload_date=now,
                update_date=now
            )
            session.add(new_file)
            session.commit()
            Logger.log_message(f"Файл {filename} добавлен в базу данных.")
            return new_file
    except Exception as e:
        session.rollback()
        Logger.log_error(f"Ошибка при создании записи файла {filename}: {str(e)}")
        return None

def create_layer_table_if_not_exists(layer_name: str) -> Optional[type]:
    """
    Создает таблицу для слоя, если она не существует
    
    Args:
        session: Сессия базы данных
        layer_name: Имя слоя
        
    Returns:
        Класс таблицы для слоя или None в случае ошибки
    """
    try:
        # Нормализуем имя таблицы (заменяем пробелы и дефисы на подчеркивания)
        table_name = layer_name.replace(' ', '_').replace('-', '_')
        
        # Проверяем существование таблицы
        inspector = inspect(engine)
        table_exists = inspector.has_table(table_name, schema='layer_schema')
        
        if not table_exists:
            # Создаем класс таблицы
            layer_class = models.create_layer_table(layer_name)
            # Создаем таблицу в базе данных
            layer_class.__table__.create(engine, checkfirst=True)
            Logger.log_message(f"Создана таблица для слоя {layer_name}")
            return layer_class
        else:
            # Возвращаем существующий класс таблицы
            return models.create_layer_table(layer_name)
    except Exception as e:
        Logger.log_error(f"Ошибка при создании таблицы для слоя {layer_name}: {str(e)}")
        return None


# ----------------------
# Методы экспорта
# ----------------------

def export_dxf_to_database(username, password, host, port, dbname, dxf_handler: DXFHandler, file_path: str, mapping_mode: str = "always_overwrite") -> bool:
    """
    Экспортирует DXF файл в базу данных
    
    Args:
        username: Имя пользователя для подключения к БД
        password: Пароль для подключения к БД
        host: Адрес сервера БД
        port: Порт сервера БД
        dbname: Имя базы данных
        dxf_handler: Экземпляр обработчика DXF
        file_path: Путь к DXF файлу
        mapping_mode: Режим маппирования слоев (always_overwrite, geometry, notes, both)

    Returns:
        True в случае успеха, иначе False
    """
    try:
        session = _connect_to_database(username, password, host, port, dbname)
        # Получаем имя файла из пути
        filename = os.path.basename(file_path)
        Logger.log_message(f"Начало экспорта DXF файла {filename} в базу данных...")
        Logger.log_message(f"Путь к файлу: {file_path}")
        Logger.log_message(f"Режим маппирования: {mapping_mode}")
        
        # Читаем содержимое файла
        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Создаем запись о файле
        file_record = create_file_record(session, filename, file_content)
        if not file_record:
            return False
        
        # Получаем слои DXF файла
        layers_entities = dxf_handler.get_entities_for_export(filename)

        # Для каждого слоя создаем таблицу и записываем сущности
        for layer_name, entities in layers_entities.items():
            layer_class = create_layer_table_if_not_exists(layer_name)
            if not layer_class:
                continue
            
            # В зависимости от режима маппирования выбираем различную стратегию
            if mapping_mode == "always_overwrite":
                # Удаляем все существующие записи для этого файла и слоя
                session.query(layer_class).filter_by(file_id=file_record.id).delete()
                session.commit()
                Logger.log_message(f"Все существующие записи для файла {filename} в слое {layer_name} удалены")
                
                # Добавляем новые записи
                _add_new_entities(session, entities, layer_class, file_record.id)
                
            elif mapping_mode in ["geometry", "notes", "both"]:
                # Получаем все существующие сущности для этого файла в данном слое
                existing_entities = session.query(layer_class).filter_by(file_id=file_record.id).all()
                
                # Обрабатываем логику маппирования
                _process_mapping(session, entities, existing_entities, layer_class, file_record.id, mapping_mode)
            
            Logger.log_message(f"Экспортирован слой {layer_name} из файла {filename}")
            
        # Генерируем превью файла
        _create_output_dxf(file_path, filename, dxf_handler)

        return True
    except Exception as e:
        session.rollback()
        Logger.log_error(f"Ошибка при экспорте DXF файла {filename} в базу данных: {str(e)}")
        return False


def _create_output_dxf(file_path : str, filename: str, dxf_handler: DXFHandler) -> None:
    """Создание SVG превью DXF файла"""
    doc = dxf_handler.simle_read_dxf_file(file_path)
    dxf_handler.save_svg_preview(doc, doc.modelspace(), filename)

def _add_new_entities(session: Session, entities, layer_class, file_id: int) -> None:
    """
    Добавляет новые сущности в таблицу слоя
    
    Args:
        session: Сессия базы данных
        entities: Список сущностей для добавления
        layer_class: Класс модели таблицы слоя
        file_id: ID файла
    """
    try:
        for entity in entities:
            # Преобразуем DXF сущность в формат PostGIS
            postgis_entity = convert_entity_to_postgis(entity)
            
            if postgis_entity:
                # Создаем новый экземпляр модели слоя
                layer_entity = layer_class(
                    file_id=file_id,
                    geom_type=postgis_entity['geom_type'],
                    geometry=postgis_entity['geometry'],
                    notes=postgis_entity.get('notes', None),
                    extra_data=postgis_entity.get('extra_data', None)
                )
                session.add(layer_entity)
        
        # Сохраняем изменения в базе данных
        session.commit()
        Logger.log_message(f"Добавлено {len(entities)} новых сущностей в слой")
    except Exception as e:
        session.rollback()
        Logger.log_error(f"Ошибка при добавлении новых сущностей: {str(e)}")

def _process_mapping(session: Session, new_entities, existing_entities: List,
                     layer_class, file_id: int, mapping_mode: str) -> None:
    """
    Обрабатывает маппирование между существующими и новыми сущностями в соответствии с выбранным режимом
    
    Args:
        session: Сессия базы данных
        new_entities: Список новых сущностей для добавления/обновления
        existing_entities: Список существующих сущностей в базе данных
        layer_class: Класс модели таблицы слоя
        file_id: ID файла
        mapping_mode: Режим маппирования (geometry, notes, both)
    """
    pass

# ----------------------
# Метод удаления
# ----------------------

def delete_dxf_file(username, password, host, port, dbname, file_id: int) -> bool:
    """
    Удаляет DXF файл из базы данных по его ID
    
    Args:
        session: Сессия базы данных
        file_id: ID файла в базе данных
        
    Returns:
        True в случае успеха, иначе False
    """
    try:
        session = _connect_to_database(username, password, host, port, dbname)
        file_record = session.query(models.DxfFile).filter_by(id=file_id).first()
        if not file_record:
            Logger.log_warning(f"Файл с ID {file_id} не найден в базе данных")
            return False
            
        # Получаем имя файла для логирования
        filename = file_record.filename
        
        # Удаляем файл
        session.delete(file_record)
        session.commit()
        
        Logger.log_message(f"Файл {filename} (ID: {file_id}) успешно удален из базы данных")
        return True
    except Exception as e:
        session.rollback()
        Logger.log_error(f"Ошибка при удалении DXF файла с ID {file_id}: {str(e)}")
        return False


# ----------------------
# Методы запросов
# ----------------------

def get_all_dxf_files(username, password, host, port, dbname):
    """
    Получает список всех DXF файлов в базе данных
    
    Args:
        session: Сессия базы данных
        
    Returns:
        Список объектов DxfFile
    """
    try:
        db = _connect_to_database(username, password, host, port, dbname)
        db_files = db.query(models.DxfFile).all()
        files = []
        for file in db_files:
            files.append({
                'id': file.id,
                'filename': file.filename,
                'upload_date': file.upload_date,
                'update_date': file.update_date
            })
        return files
    except Exception as e:
        Logger.log_error(f"Ошибка при получении списка DXF файлов: {str(e)}")
        return []

def get_dxf_file_by_id(username, password, host, port, dbname, file_id: int) -> Optional[models.DxfFile]:
    """
    Получает DXF файл по его ID
    
    Args:
        session: Сессия базы данных
        file_id: ID файла
        
    Returns:
        Объект DxfFile или None, если файл не найден
    """
    try:
        session = _connect_to_database(username, password, host, port, dbname)
        return session.query(models.DxfFile).filter_by(id=file_id).first()
    except Exception as e:
        Logger.log_error(f"Ошибка при получении DXF файла с ID {file_id}: {str(e)}")
        return None

def get_dxf_file_by_name(session: Session, filename: str) -> Optional[models.DxfFile]:
    """
    Получает DXF файл по его имени
    
    Args:
        session: Сессия базы данных
        filename: Имя файла
        
    Returns:
        Объект DxfFile или None, если файл не найден
    """
    try:
        return session.query(models.DxfFile).filter_by(filename=filename).first()
    except Exception as e:
        Logger.log_error(f"Ошибка при получении DXF файла с именем {filename}: {str(e)}")
        return None

def get_layer_entities(username, password, host, port, dbname, file_id: int, layer_name: str) -> List[dict]:
    """
    Получает все сущности указанного слоя для файла
    
    Args:
        session: Сессия базы данных
        file_id: ID файла
        layer_name: Имя слоя
        
    Returns:
        Список сущностей с их геометрией и дополнительными данными
    """
    try:
        session = _connect_to_database(username, password, host, port, dbname)
                # Получаем класс таблицы для слоя
        layer_class = models.create_layer_table(layer_name)
        
        # Выполняем запрос
        entities = session.query(layer_class).filter_by(file_id=file_id).all()
        
        # Преобразуем результаты в удобный формат
        result = []
        for entity in entities:
            # Конвертируем геометрию из WKB в объект Shapely
            shapely_geom = to_shape(entity.geometry)
            
            # Формируем словарь с данными
            entity_data = {
                'id': entity.id,
                'geom_type': entity.geom_type,
                'geometry': shapely_geom,
                'notes': entity.notes,
                'extra_data': entity.extra_data
            }
            
            result.append(entity_data)
            
        return result
    except Exception as e:
        Logger.log_error(f"Ошибка при получении сущностей слоя {layer_name} для файла с ID {file_id}: {str(e)}")
        return []

def get_all_layers_for_file(username, password, host, port, dbname, file_id: int) -> List[str]:
    """
    Получает список всех слоев для указанного файла
    
    Args:
        session: Сессия базы данных
        file_id: ID файла
        
    Returns:
        Список имен слоев
    """
    try:
        session = _connect_to_database(username, password, host, port, dbname)
                # Получаем метаданные базы данных
        metadata = MetaData(schema='layer_schema')
        metadata.reflect(bind=engine)
        
        # Получаем все таблицы в схеме layer_schema
        layer_tables = [table for table in metadata.tables.values()]
        
        # Список для хранения имен слоев
        layers = []
        
        # Проверяем каждую таблицу на наличие сущностей для указанного файла
        for table in layer_tables:
            # Формируем запрос
            query = select([table]).where(table.c.file_id == file_id).limit(1)
            
            # Выполняем запрос
            result = session.execute(query).fetchone()
            
            # Если есть результаты, добавляем имя таблицы в список слоев
            if result:
                # Преобразуем имя таблицы обратно в имя слоя (заменяем подчеркивания на пробелы)
                layer_name = table.name  # Можно также сделать замену: .replace('_', ' ')
                layers.append(layer_name)
        
        return layers
    except Exception as e:
        Logger.log_error(f"Ошибка при получении списка слоев для файла с ID {file_id}: {str(e)}")
        return []

# ----------------------
# Методы очистки базы данных
# ----------------------

def drop_all_tables(enginee: Engine) -> Session:
    """
    Удаляет все таблицы и схемы, связанные с DXF-PostGIS-Converter
    
    Args:
        session: Сессия базы данных
        
    Returns:
        True в случае успеха, иначе False
    """
    try:
        global SessionLocal
        global engine
        engine = enginee
        # Закрываем все активные сессии
        close_all_sessions()
        
        # Получаем подключение к базе данных
        connection = engine.connect()
        
        # Лог о начале процедуры
        Logger.log_message("Начало процедуры удаления всех таблиц и схем...")
        
        # Удаляем все таблицы в схеме layer_schema
        try:
            Logger.log_message("Удаление таблиц слоев...")
            
            # Получаем метаданные таблиц в схеме layer_schema
            metadata = MetaData(schema='layer_schema')
            metadata.reflect(bind=engine)
            
            # Удаляем каждую таблицу
            for table in reversed(metadata.sorted_tables):
                Logger.log_message(f"Удаление таблицы {table.name} из схемы layer_schema...")
                connection.execute(text(f'DROP TABLE IF EXISTS layer_schema."{table.name}" CASCADE;'))
            
            connection.commit()
            Logger.log_message("Таблицы слоев успешно удалены.")
        except Exception as e:
            connection.rollback()
            Logger.log_error(f"Ошибка при удалении таблиц слоев: {str(e)}")
            # Продолжаем выполнение, чтобы попытаться удалить остальные объекты
        
        # Удаляем таблицы в схеме file_schema
        try:
            Logger.log_message("Удаление таблиц файлов...")
            
            # Получаем метаданные таблиц в схеме file_schema
            metadata = MetaData(schema='file_schema')
            metadata.reflect(bind=engine)
            
            # Удаляем каждую таблицу
            for table in reversed(metadata.sorted_tables):
                Logger.log_message(f"Удаление таблицы {table.name} из схемы file_schema...")
                connection.execute(text(f'DROP TABLE IF EXISTS file_schema."{table.name}" CASCADE;'))
            
            connection.commit()
            Logger.log_message("Таблицы файлов успешно удалены.")
        except Exception as e:
            connection.rollback()
            Logger.log_error(f"Ошибка при удалении таблиц файлов: {str(e)}")
            # Продолжаем выполнение, чтобы попытаться удалить остальные объекты
        
        # Удаляем схемы
        try:
            Logger.log_message("Удаление схем...")
            connection.execute(text("DROP SCHEMA IF EXISTS layer_schema CASCADE;"))
            connection.execute(text("DROP SCHEMA IF EXISTS file_schema CASCADE;"))
            connection.commit()
            Logger.log_message("Схемы успешно удалены.")
        except Exception as e:
            connection.rollback()
            Logger.log_error(f"Ошибка при удалении схем: {str(e)}")
            # Продолжаем выполнение
        
        # Удаляем все последовательности и функции
        try:
            Logger.log_message("Удаление последовательностей и функций...")
            
            # Удаляем все последовательности
            connection.execute(text("""
                DO $$
                DECLARE
                    seq record;
                BEGIN
                    FOR seq IN (
                        SELECT sequence_schema, sequence_name
                        FROM information_schema.sequences
                        WHERE sequence_schema IN ('layer_schema', 'file_schema')
                    )
                    LOOP
                        EXECUTE format('DROP SEQUENCE IF EXISTS %I.%I CASCADE', seq.sequence_schema, seq.sequence_name);
                    END LOOP;
                END$$;
            """))
            
            # Удаляем все функции
            connection.execute(text("""
                DO $$
                DECLARE
                    func record;
                BEGIN
                    FOR func IN (
                        SELECT n.nspname as schema_name, p.proname as function_name, 
                               pg_get_function_identity_arguments(p.oid) as args
                        FROM pg_proc p
                        JOIN pg_namespace n ON p.pronamespace = n.oid
                        WHERE n.nspname IN ('layer_schema', 'file_schema')
                    )
                    LOOP
                        EXECUTE format('DROP FUNCTION IF EXISTS %I.%I(%s) CASCADE', 
                                      func.schema_name, func.function_name, func.args);
                    END LOOP;
                END$$;
            """))
            
            connection.commit()
            Logger.log_message("Последовательности и функции успешно удалены.")
        except Exception as e:
            connection.rollback()
            Logger.log_error(f"Ошибка при удалении последовательностей и функций: {str(e)}")
        
        # Очищаем кэш файлов
        _files_cache.clear()
        
        # Создаем схемы заново, чтобы база была готова к работе
        _create_schemas()
        
        # Создаем таблицы заново
        Base.metadata.create_all(bind=engine)
        
        connection.close()
        
        # Создаем новую сессию
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        Logger.log_message("База данных успешно очищена и подготовлена к работе.")
        return SessionLocal()
    except Exception as e:
        Logger.log_error(f"Критическая ошибка при удалении базы данных: {str(e)}")
        return None
