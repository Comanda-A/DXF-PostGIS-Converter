from sqlalchemy.orm import declarative_base
Base = declarative_base()

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session, close_all_sessions
from geoalchemy2.shape import from_shape
from ..logger.logger import Logger
from datetime import datetime, timezone
from . import models
from .converter_dxf_to_postgis import convert_dxf_to_postgis, convert_postgis_to_dxf, _replace_vec3_to_list
from ..dxf.dxf_handler import DXFHandler

# Шаблон URL для подключения к базе данных
PATTERN_DATABASE_URL = 'postgresql://{username}:{password}@{address}:{port}/{dbname}'

# Глобальная переменная для хранения текущего движка и сессии
engine: Engine = None
SessionLocal: sessionmaker[Session] = None

def _connect_to_database(username, password, address, port, dbname):
    """Создание подключения к базе данных"""
    try:
        global engine, SessionLocal

        # Закрываем текущие сессии, если они есть
        if SessionLocal:
            close_all_sessions()

        # Формируем URL базы данных
        db_url = PATTERN_DATABASE_URL.format(
            username=username,
            password=password,
            address=address,
            port=port,
            dbname=dbname
        )

        # Создаем новый движок и сессию
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # Создаем все таблицы, если их нет
        Base.metadata.create_all(bind=engine)

        # Логируем успешное подключение
        Logger.log_message(f"Подключено к базе данных PostgreSQL '{dbname}' по адресу {address}:{port} с пользователем '{username}'.")

        return SessionLocal()
    except Exception as e:
        Logger.log_error(f"Ошибка подключения к базе данных PostgreSQL '{dbname}' по адресу {address}:{port} с пользователем '{username}'.")
        return None

def _create_file(db: Session, file_name: str, dxf_handler: DXFHandler) -> models.File:
    """Создание записи файла в базе данных"""
    db_file = db.query(models.File).filter(models.File.filename == file_name).first()
    if db_file is not None:
        return db_file
    else:
        meta = dxf_handler.get_file_metadata(file_name)
        styles_meta = dxf_handler.extract_styles(file_name)
        tables_meta = dxf_handler.get_tables(file_name)
        blocks_meta = dxf_handler.extract_blocks_from_dxf(file_name)

        meta["tables"] = tables_meta.get("tables", {})
        meta["blocks"] = blocks_meta
        meta["styles"] = styles_meta
        # Конвертируем Vec3 в список
        meta = _replace_vec3_to_list(meta)
        db_file = models.File(
            filename=file_name,
            file_metadata=meta,
            upload_date=datetime.now(timezone.utc),
            update_date=datetime.now(timezone.utc)
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        return db_file

def _create_layer(db: Session, file_id: int, file_name: str, layer_name: str, dxf_handler: DXFHandler, description: str = '') -> models.Layer:
    """Создание записи слоя в базе данных"""
    db_layer = db.query(models.Layer).filter(models.Layer.file_id == file_id, models.Layer.name == layer_name).first()
    if db_layer is not None:
        return db_layer
    else:
        db_layer = models.Layer(
            file_id=file_id,
            name=layer_name,
            description=description,
            layer_metadata=dxf_handler.get_layer_metadata(file_name, layer_name)
        )
        db.add(db_layer)
        db.commit()
        db.refresh(db_layer)
        return db_layer

def _handle_existing_file(db: Session, table_info: dict, username: str, password: str, address: str, port: str, dbname: str) -> Session:
    """Обработка существующего файла в зависимости от режима импорта"""
    if table_info['import_mode'] == 'overwrite':
        file_id = table_info['file_id']
        delete_dxf(username, password, address, port, dbname, file_id)
        return _connect_to_database(username, password, address, port, dbname)
    elif table_info['import_mode'] == 'mapping':
        _update_mappings(db, table_info)
        return db
    return db

def _update_mappings(db: Session, table_info: dict) -> None:
    """Обновление геометрических и негеометрических сопоставлений"""
    geom_mappings = table_info.get('geom_mappings', {})
    nongeom_mappings = table_info.get('nongeom_mappings', {})
    
    for mappings, model_class in [(geom_mappings, models.GeometricObject), 
                                 (nongeom_mappings, models.NonGeometricObject)]:
        for _, mapping in mappings.items():
            if 'entity_id' in mapping and 'attributes' in mapping:
                obj = db.query(model_class).filter(model_class.id == mapping['entity_id']).first()
                if obj and mapping['attributes']:
                    extra_data = obj.extra_data
                    if 'attributes' not in extra_data:
                        extra_data['attributes'] = {}
                    extra_data['attributes'].update(mapping['attributes'])
                    obj.extra_data = extra_data
    
    db.commit()

def _process_layer_entities(db: Session, db_file: models.File, filename: str, layer_name: str, 
                          layer_entities: list, dxf_handler: DXFHandler) -> None:
    """Обработка объектов для определенного слоя"""
    db_layer = _create_layer(db, db_file.id, filename, layer_name, dxf_handler)
    for entity in layer_entities:
        geom_type, geometry, extra_data = convert_dxf_to_postgis(entity, dxf_handler)
        object_class = models.NonGeometricObject if geometry is None else models.GeometricObject
        object_data = {
            'file_id': db_file.id,
            'layer_id': db_layer.id,
            'geom_type': geom_type,
            'extra_data': extra_data
        }
        if geometry is not None:
            object_data['geometry'] = from_shape(geometry, srid=4326)
        
        db.add(object_class(**object_data))

def _create_output_dxf(db: Session, db_file: models.File, filename: str, dxf_handler: DXFHandler) -> None:
    """Создание выходного DXF файла и SVG предпросмотра"""
    file_metadata = db_file.file_metadata
    layers = db.query(models.Layer).filter(models.Layer.file_id == db_file.id).all()
    geom_objects = db.query(models.GeometricObject).filter(models.GeometricObject.file_id == db_file.id).all()
    non_geom_objects = db.query(models.NonGeometricObject).filter(models.NonGeometricObject.file_id == db_file.id).all()

    original_path = dxf_handler.get_file_path(filename)
    output_path = original_path.replace('.dxf', '_exported.dxf')

    convert_postgis_to_dxf(file_metadata, layers, geom_objects, non_geom_objects, output_path)
    doc = dxf_handler.simle_read_dxf_file(output_path)
    dxf_handler.save_svg_preview(doc, doc.modelspace(), filename)

    import os
    if os.path.exists(output_path):
        os.remove(output_path)

def export_dxf(username: str, password: str, address: str, port: str, dbname: str, 
               dxf_handler: DXFHandler, table_info: dict) -> None:
    """Экспорт данных DXF в базу данных с поддержкой сопоставления"""
    db = _connect_to_database(username, password, address, port, dbname)
    if not db:
        Logger.log_error("Не удалось подключиться к базе данных")
        return
    
    try:
        if not table_info['is_new_file']:
            db = _handle_existing_file(db, table_info, username, password, address, port, dbname)
            if table_info['import_mode'] == 'mapping':
                Logger.log_message("Успешно экспортированы данные DXF в базу данных")
                return

        for filename, dxf_drawing in dxf_handler.dxf.items():
            db_file = _create_file(db, filename, dxf_handler)
            entities_to_export = dxf_handler.get_entities_for_export(filename)

            if dxf_handler.selected_entities:

                # Группировка объектов по слоям
                layers_entities = {}
                for entity in entities_to_export:
                    layer_name = entity.dxf.layer
                    if layer_name not in layers_entities:
                        layers_entities[layer_name] = []
                    layers_entities[layer_name].append(entity)
                entities_to_export = layers_entities

            for layer_name, layer_entities in entities_to_export.items():
                _process_layer_entities(db, db_file, filename, layer_name, layer_entities, dxf_handler)
            
            db.commit()
            _create_output_dxf(db, db_file, filename, dxf_handler)

        Logger.log_message("Успешно экспортированы данные DXF в базу данных")
        
    except Exception as e:
        db.rollback()
        Logger.log_error(f"Ошибка экспорта данных DXF: {str(e)}")
    finally:
        db.close()

def import_dxf(username: str, password: str, address: str, port: str, dbname: str, file_id: int, path: str):
    """Импорт DXF из базы данных"""
    db = _connect_to_database(username, password, address, port, dbname)  # Получаем сессию
    file_metadata = db.query(models.File).filter(models.File.id == file_id).first().file_metadata
    layers = db.query(models.Layer).filter(models.Layer.file_id == file_id).all()
    geom_objects = db.query(models.GeometricObject).filter(models.GeometricObject.file_id == file_id).all()
    non_geom_objects = db.query(models.NonGeometricObject).filter(models.NonGeometricObject.file_id == file_id).all()

    # Вызываем функцию конверта данных в DXF
    convert_postgis_to_dxf(file_metadata, layers, geom_objects, non_geom_objects, path)

def delete_dxf(username: str, password: str, address: str, port: str, dbname: str, file_id: int):
    """Удаление DXF файла и связанных данных из базы"""
    db = _connect_to_database(username, password, address, port, dbname)
    file = db.query(models.File).filter(models.File.id == file_id).first()
    layers = db.query(models.Layer).filter(models.Layer.file_id == file_id).all()
    geom_objects = db.query(models.GeometricObject).filter(models.GeometricObject.file_id == file_id).all()
    non_geom_objects = db.query(models.NonGeometricObject).filter(models.NonGeometricObject.file_id == file_id).all()

    for obj in non_geom_objects:
        db.delete(obj)

    for obj in geom_objects:
        db.delete(obj)

    for layer in layers:
        db.delete(layer)

    db.delete(file)
    db.commit()

def get_all_files_from_db(username, password, address, port, dbname):
    """Получение списка всех файлов из базы данных"""
    db = _connect_to_database(username, password, address, port, dbname)
    if db is None:
        return None

    try:
        db_files = db.query(models.File).all()
        files = []
        for file in db_files:
            try:
                if isinstance(file.filename, bytes):
                    filename = file.filename.decode('utf-8', errors='replace')
                else:
                    filename = file.filename
                    
                files.append({
                    'id': file.id,
                    'filename': filename,
                    'upload_date': file.upload_date,
                    'update_date': file.update_date
                })
            except Exception as e:
                Logger.log_error(f"Ошибка обработки файла {file.id}: {str(e)}")
                continue
                
        return files
    except Exception as e:
        Logger.log_error(f"Ошибка получения файлов из базы данных: {str(e)}")
        return None
    finally:
        db.close()

def get_all_file_layers_from_db(username, password, address, port, dbname, file_id):
    """Получение всех слоев определенного файла"""
    db = _connect_to_database(username, password, address, port, dbname)
    if db is None:
        return None

    try:
        # Используем модель Layer для получения слоёв
        db_layers = db.query(models.Layer).filter(models.Layer.file_id == file_id).all()
        
        layers = []
        for layer in db_layers:
            try:
                # Преобразуем название слоя из bytes если нужно
                name = layer.name.decode('utf-8', errors='replace') if isinstance(layer.name, bytes) else layer.name
                
                layers.append({
                    'id': layer.id,
                    'file_id': layer.file_id,
                    'name': name,
                    'color': layer.color,
                    'description': layer.description,
                    'layer_metadata': layer.layer_metadata
                })
            except Exception as e:
                Logger.log_error(f"Ошибка обработки слоя {layer.id}: {str(e)}")
                continue
                
        return layers
    except Exception as e:
        Logger.log_error(f"Ошибка получения слоев из базы данных: {str(e)}")
        return None
    finally:
        db.close()

def get_layer_objects(username, password, address, port, dbname, layer_id):
    """Получение всех геометрических и негеометрических объектов для слоя"""
    db = _connect_to_database(username, password, address, port, dbname)
    if db is None:
        return None

    try:
        cur = db.get_bind().raw_connection().cursor()
        combined_query = """
            (SELECT id, geom_type, extra_data, 'geometric' as obj_type
             FROM geometric_objects 
             WHERE layer_id = %s)
            UNION ALL
            (SELECT id, geom_type, extra_data, 'non_geometric' as obj_type
             FROM non_geometric_objects 
             WHERE layer_id = %s)
        """
        cur.execute(combined_query, (layer_id, layer_id))
        results = cur.fetchall()
        cur.close()
        return results
    except Exception as e:
        Logger.log_error(f"Ошибка получения объектов слоя: {str(e)}")
        return None
    finally:
        db.close()

def get_layers_for_file(username, password, address, port, dbname, file_id):
    """Получение слоев для определенного файла"""
    db = _connect_to_database(username, password, address, port, dbname)
    if db is None:
        return None

    try:
        cur = db.get_bind().raw_connection().cursor()
        query = """
            SELECT l.id, l.name, l.color, l.description, l.layer_metadata
            FROM layers l
            WHERE l.file_id = %s
            ORDER BY l.name;
        """
        cur.execute(query, (file_id,))
        layers = cur.fetchall()
        cur.close()
        return layers
    except Exception as e:
        Logger.log_error(f"Ошибка получения слоев: {str(e)}")
        return None
    finally:
        db.close()

def get_table_fields(username, password, address, port, dbname, schema_name, table_name):
    """Получение всех негеометрических полей для таблицы"""
    db = _connect_to_database(username, password, address, port, dbname)
    if db is None:
        return None

    try:
        cur = db.get_bind().raw_connection().cursor()
        query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = %s 
            AND table_name = %s
            AND column_name NOT IN (
                SELECT f_geometry_column 
                FROM geometry_columns 
                WHERE f_table_schema = %s 
                AND f_table_name = %s
            )
        """
        cur.execute(query, (schema_name, table_name, schema_name, table_name))
        results = cur.fetchall()
        cur.close()
        
        # Конвертируем результат в список
        return [row[0] for row in results]
    except Exception as e:
        Logger.log_error(f"Ошибка получения полей таблицы: {str(e)}")
        return None
    finally:
        db.close()
