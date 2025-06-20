from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text, Table, MetaData, LargeBinary
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from .database import Base
from ..logger.logger import Logger


# Базовый класс для файлов DXF
class DxfFileBase:
    """ Базовый класс для создания таблиц файлов DXF """
    
    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False, unique=True)
    file_content = Column(LargeBinary, nullable=False)  # Хранение самого файла в бинарном формате
    upload_date = Column(DateTime)
    update_date = Column(DateTime)


# Schema для файлов DXF (совместимость с существующим кодом)
class DxfFile(Base, DxfFileBase):
    """ Таблица для хранения целых DXF файлов """
    
    __tablename__ = 'dxf_files'
    __table_args__ = {'schema': 'file_schema'}


def create_file_table(schema_name='file_schema'):
    """
    Создает класс таблицы для файлов DXF в указанной схеме
    
    Args:
        schema_name: Имя схемы для размещения таблицы
        
    Returns:
        Класс таблицы SQLAlchemy для файлов
    """
    Logger.log_message(f"Creating file table in schema '{schema_name}'")
    
    return type(
        f"DxfFile_{schema_name}",
        (Base, DxfFileBase),
        {
            '__tablename__': 'dxf_files',
            '__table_args__': {'schema': schema_name, 'extend_existing': True}
        }
    )


# Базовый класс для слоев DXF - будет использоваться для создания таблиц для каждого слоя
class DxfLayerBase:
    """ Базовый класс для создания таблиц слоев DXF """
    
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, nullable=True)  # Будет установлен ForeignKey при создании таблицы
    geometry = Column(Geometry('GEOMETRYZ', srid=4326), nullable=False)
    geom_type = Column(String, nullable=False)
    notes = Column(Text, nullable=True, comment='Примечание к элементу (связанные негеометрические объекты)')
    extra_data = Column(JSONB, nullable=True)


# Функция для динамического создания таблицы слоя
def create_layer_table(layer_name, schema_name='layer_schema', file_schema='file_schema'):
    """
    Создает класс таблицы для указанного слоя DXF
    
    Args:
        layer_name: Имя слоя, для которого создается таблица
        schema_name: Имя схемы для размещения таблицы
        file_schema: Имя схемы где находится таблица файлов
        
    Returns:
        Класс таблицы SQLAlchemy для данного слоя
    """
    # Заменяем пробелы и дефисы на подчеркивания
    tablename = layer_name.replace(' ', '_').replace('-', '_')

    # Добавим отладочную информацию о длине имени таблицы
    Logger.log_message(f"Creating table for layer '{layer_name}' with tablename '{tablename}' in schema '{schema_name}' (win1251 length: {len(tablename.encode('cp1251'))}, char length: {len(tablename)})")
    
    # Создаем атрибуты для класса
    attributes = {
        '__tablename__': tablename,
        '__table_args__': {'schema': schema_name, 'extend_existing': True},
        'id': Column(Integer, primary_key=True),
        'file_id': Column(Integer, ForeignKey(f'{file_schema}.dxf_files.id', ondelete='CASCADE'), nullable=True),
        'geometry': Column(Geometry('GEOMETRYZ', srid=4326), nullable=False),
        'geom_type': Column(String, nullable=False),
        'notes': Column(Text, nullable=True, comment='Примечание к элементу (связанные негеометрические объекты)'),
        'extra_data': Column(JSONB, nullable=True),
    }
    
    return type(
        f"{layer_name}",
        (Base,),
        attributes
    )
