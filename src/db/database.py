
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from geoalchemy2.shape import from_shape
from ..logger.logger import Logger
from datetime import datetime, timezone
from . import models
from .converter_dxf_to_postgis import convert_dxf_to_postgis


PATTERN_DATABASE_URL = 'postgresql://{username}:{password}@{address}:{port}/{dbname}'


# Глобальная переменная для хранения текущего движка и сессии
engine: Engine = None
SessionLocal: sessionmaker[Session] = None


# Функция для создания нового движка и сессии
def connect_to_database(username, password, address, port, dbname):
    try:
        global engine, SessionLocal

        # Закрываем текущие сессии, если они есть
        if SessionLocal:
            SessionLocal.close_all()

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

        # Логируем успешное подключение
        Logger.log_message(f"Connected to PostgreSQL database '{dbname}' at {address}:{port} as user '{username}'.")

        # Создаем все таблицы, если нужно
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        Logger.log_error(f'Database connection error: {e}')


def send_layers_to_db(file_name: str = '', layers: dict = None):
    db = SessionLocal()  # Получаем сессию
    try:
        
        db_file = db.query(models.File).filter(models.File.filename == file_name).first()
        if db_file:
            return

        # создаем файл
        db_file = models.File(
            filename=file_name,
            upload_date = datetime.now(timezone.utc),
            update_date = datetime.now(timezone.utc)
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)

        Logger.log_message(f'file done')

        # сохраняем слои
        for layer_name, entities in layers.items():
            
            # создание слоя
            layer = models.Layer(
                file_id=db_file.id,
                name=layer_name,
                description=''
            )
            
            # сохранение слоя
            db.add(layer)
            db.commit()
            db.refresh(layer)

            Logger.log_message(f'layer done')

            # сохранение объектов
            for entity in entities:
                # конверт в postgis object
                Logger.log_message(str(entity))
                postgis_object = convert_dxf_to_postgis(entity)

                if postgis_object is None:
                    #создание объекта
                    object = models.NonGeometricObject(
                        layer_id=layer.id,
                        geom_type=entity['entity_description'],
                        geometry=entity
                    )
                    # сохранение объекта
                    db.add(object)
                else:
                    #создание объекта
                    object = models.GeometricObject(
                        layer_id=layer.id,
                        geom_type=str(entity['entity_description']),
                        geometry=from_shape(postgis_object, srid=4326)
                    )
                    # сохранение объекта
                    db.add(object)
                    db.commit()
                    db.refresh(object)

                    # создание атрибутов
                    attributes = models.Attribute(object_id=object.id, value=entity['attributes'])
                    db.add(attributes)

                    # создание геометрии
                    geometry = models.Geometry(object_id=object.id, value=entity['geometry'])
                    db.add(geometry)

                Logger.log_message(f'obj done')

                # сейв
                db.commit()

        Logger.log_message(f'Successfully saved layers and entities from {file_name} to database.')
    except Exception as e:
        Logger.log_error(f'Error saving layers to database: {e}')
    finally:
        db.close()  # Закрываем сессию
