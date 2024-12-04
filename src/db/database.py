
from sqlalchemy.orm import declarative_base
Base = declarative_base()

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session, close_all_sessions
from geoalchemy2.shape import from_shape
from ..logger.logger import Logger
from datetime import datetime, timezone
from . import models
from .converter_dxf_to_postgis import convert_dxf_to_postgis, convert_postgis_to_dxf
from ..dxf.dxf_handler import DXFHandler
from ..tree_widget_handler import TreeWidgetHandler


PATTERN_DATABASE_URL = 'postgresql://{username}:{password}@{address}:{port}/{dbname}'


# Глобальная переменная для хранения текущего движка и сессии
engine: Engine = None
SessionLocal: sessionmaker[Session] = None


# Функция для создания нового движка и сессии
def _connect_to_database(username, password, address, port, dbname):
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

        # Создаем все таблицы, если нужно
        Base.metadata.create_all(bind=engine)

        # Логируем успешное подключение
        Logger.log_message(f"Connected to PostgreSQL database '{dbname}' at {address}:{port} as user '{username}'.")

        return SessionLocal()
    except Exception as e:
        Logger.log_error("Error connection to PostgreSQL database '{dbname}' at {address}:{port} as user '{username}'.")
        return None


def _create_file(db: Session, file_name: str, dxf_handler: DXFHandler) -> models.File:
    db_file = db.query(models.File).filter(models.File.filename == file_name).first()
    if db_file is not None:
        return db_file
    else:
        db_file = models.File(
            filename=file_name,
            file_metadata=dxf_handler.get_file_metadata(file_name),
            upload_date = datetime.now(timezone.utc),
            update_date = datetime.now(timezone.utc)
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        return db_file


def _create_layer(db: Session, file_id: int, file_name: str, layer_name: str, dxf_handler: DXFHandler, description: str = '') -> models.Layer:
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


def export_dxf(
    username: str,                  # для коннекта к бд
    password: str,                  # для коннекта к бд
    address: str,                   # для коннекта к бд
    port: str,                      # для коннекта к бд
    dbname: str,                    # для коннекта к бд
    dxf_handler: DXFHandler,        # dxf
    #tree_widget: TreeWidgetHandler  # tree_widget
):
    
    db = _connect_to_database(username, password, address, port, dbname)  # Получаем сессию

    for filename, dxf_drawing in dxf_handler.dxf.items():
        db_file = _create_file(db, filename, dxf_handler) # создаем файл в бд
        for layer_name, layer_entities in dxf_handler.get_layers(filename).items():
            db_layer = _create_layer(db, db_file.id, filename, layer_name, dxf_handler)
            for entity in layer_entities:
                geom_type, geometry, extra_data = convert_dxf_to_postgis(entity)
                if geometry is None:
                    object = models.NonGeometricObject(
                        file_id=db_file.id,
                        layer_id=db_layer.id,
                        geom_type=geom_type,
                        extra_data=extra_data
                    )
                else:
                    object = models.GeometricObject(
                        file_id=db_file.id,
                        layer_id=db_layer.id,
                        geom_type=geom_type,
                        geometry=from_shape(geometry, srid=4326),
                        extra_data=extra_data
                    )

                db.add(object)


    db.commit()
    db.close()

    '''
                # сейв
                db.commit()

        Logger.log_message(f'Successfully saved layers and entities from {file_name} to database.')
    except Exception as e:
        Logger.log_error(f'Error saving layers to database: {e}')
    finally:
        db.close()  # Закрываем сессию
    '''


def import_dxf(
    username: str,                  # для коннекта к бд
    password: str,                  # для коннекта к бд
    address: str,                   # для коннекта к бд
    port: str,                      # для коннекта к бд
    dbname: str,                    # для коннекта к бд
    file_id: int,                   # file id
    path: str                       # path
    #tree_widget: TreeWidgetHandler  # tree_widget
):
    db = _connect_to_database(username, password, address, port, dbname)  # Получаем сессию
    file_metadata = db.query(models.File).filter(models.File.id == file_id).first().file_metadata
    layers = db.query(models.Layer).filter(models.Layer.file_id == file_id).all()
    geom_objects = db.query(models.GeometricObject).filter(models.GeometricObject.file_id == file_id).all()
    non_geom_objects = db.query(models.NonGeometricObject).filter(models.NonGeometricObject.file_id == file_id).all()

    # Вызываем функцию конверта данных в DXF
    convert_postgis_to_dxf(file_metadata, layers, geom_objects, non_geom_objects, path)


def delete_dxf(
    username: str,                  # для коннекта к бд
    password: str,                  # для коннекта к бд
    address: str,                   # для коннекта к бд
    port: str,                      # для коннекта к бд
    dbname: str,                    # для коннекта к бд
    file_id: int                    # file id
):
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


def get_all_files_from_db(
    username: str,                  # для коннекта к бд
    password: str,                  # для коннекта к бд
    address: str,                   # для коннекта к бд
    port: str,                      # для коннекта к бд
    dbname: str,                    # для коннекта к бд
):
    db = _connect_to_database(username, password, address, port, dbname)  # Получаем сессию

    if db is None:
        return None

    db_files = db.query(models.File).all()
    files = [
        {
            'id': file.id,
            'filename': file.filename,
            'upload_date': file.upload_date,
            'upload_date': file.update_date
        } 
        for file in db_files
    ]
    return files


def get_all_file_layers_from_db(
    username: str,                  # для коннекта к бд
    password: str,                  # для коннекта к бд
    address: str,                   # для коннекта к бд
    port: str,                      # для коннекта к бд
    dbname: str,                    # для коннекта к бд
    file_id: int                    # id файла
):
    db = _connect_to_database(username, password, address, port, dbname)  # Получаем сессию

    if db is None:
        return None

    db_layers = db.query(models.Layer).filter(models.Layer.file_id == file_id).all()
    layers = [
        {
            'id': layer.id,
            'file_id': layer.file_id,
            'name': layer.name,
            'color': layer.color,
            'description': layer.description
        } 
        for layer in db_layers
    ]
    return layers



