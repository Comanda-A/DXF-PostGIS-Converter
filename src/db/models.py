from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text, Table, MetaData, LargeBinary
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from .database import Base
from ..logger.logger import Logger


# Schema для файлов DXF
class DxfFile(Base):
    """ Таблица для хранения целых DXF файлов """
    
    __tablename__ = 'dxf_files'
    __table_args__ = {'schema': 'file_schema'}
    
    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False, unique=True)
    file_content = Column(LargeBinary, nullable=False)  # Хранение самого файла в бинарном формате
    upload_date = Column(DateTime)
    update_date = Column(DateTime)


# Базовый класс для слоев DXF - будет использоваться для создания таблиц для каждого слоя
class DxfLayerBase:
    """ Базовый класс для создания таблиц слоев DXF """
    
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('file_schema.dxf_files.id', ondelete='CASCADE'), nullable=False)
    geometry = Column(Geometry('GEOMETRYZ', srid=4326), nullable=False)
    geom_type = Column(String, nullable=False)
    notes = Column(Text, nullable=True, comment='Примечание к элементу (связанные негеометрические объекты)')
    extra_data = Column(JSONB, nullable=True)


# Функция для динамического создания таблицы слоя
def create_layer_table(layer_name):
    """
    Создает класс таблицы для указанного слоя DXF
    
    Args:
        layer_name: Имя слоя, для которого создается таблица
        
    Returns:
        Класс таблицы SQLAlchemy для данного слоя
    """
    # Заменяем пробелы и дефисы на подчеркивания
    tablename = layer_name.replace(' ', '_').replace('-', '_')

    # Добавим отладочную информацию о длине имени таблицы
    Logger.log_message(f"Creating table for layer '{layer_name}' with tablename '{tablename}' (win1251 length: {len(tablename.encode('cp1251'))}, char length: {len(tablename)})")
    
    return type(
        f"{layer_name}",
        (Base, DxfLayerBase),
        {
            '__tablename__': tablename,
            '__table_args__': {'schema': 'layer_schema', 'extend_existing': True}
        }
    )
