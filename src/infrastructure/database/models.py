from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, LargeBinary
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
from .base import Base
from ...logger.logger import Logger


class ModelFactory:
    """Фабрика для создания моделей баз данных"""
    
    # Кэш созданных классов для предотвращения дублирования
    _file_table_cache = {}
    _layer_table_cache = {}

    @staticmethod
    def create_file_table(schema_name='file_schema'):
        """
        Создает класс таблицы для файлов DXF в указанной схеме

        Args:
            schema_name: Имя схемы для размещения таблицы

        Returns:
            Класс таблицы SQLAlchemy для файлов
        """
        # Проверяем кэш
        if schema_name in ModelFactory._file_table_cache:
            return ModelFactory._file_table_cache[schema_name]
        
        Logger.log_message(f"Creating file table in schema '{schema_name}'")

        file_class = type(
            f"DxfFile_{schema_name}",
            (Base, DxfFileBase),
            {
                '__tablename__': 'dxf_files',
                '__table_args__': {'schema': schema_name, 'extend_existing': True}
            }
        )
        
        # Сохраняем в кэш
        ModelFactory._file_table_cache[schema_name] = file_class
        return file_class

    @staticmethod
    def create_layer_table(layer_name, schema_name='layer_schema', file_schema='file_schema'):
        """
        Создает класс таблицы для указанного слоя DXF

        Args:
            layer_name: Имя слоя, для которого создается таблица
            schema_name: Имя схемы для размещения таблицы
            file_schema: Имя схемы, где находится таблица файлов

        Returns:
            Класс таблицы SQLAlchemy для данного слоя
        """
        # Создаем уникальный ключ для кэша
        cache_key = f"{schema_name}.{layer_name}"
        if cache_key in ModelFactory._layer_table_cache:
            return ModelFactory._layer_table_cache[cache_key]
        
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

        layer_class = type(
            f"{layer_name}",
            (Base,),
            attributes
        )
        
        # Сохраняем в кэш
        ModelFactory._layer_table_cache[cache_key] = layer_class
        return layer_class

# ----------------------
# Base classes for model definitions
# ----------------------

class DxfFileBase:
    """ Базовый класс для создания таблиц файлов DXF """

    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False, unique=True)
    file_content = Column(LargeBinary, nullable=False)  # Хранение самого файла в бинарном формате
    upload_date = Column(DateTime)
    update_date = Column(DateTime)


class DxfLayerBase:
    """ Базовый класс для создания таблиц слоев DXF """

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, nullable=True)  # Будет установлен ForeignKey при создании таблицы
    geometry = Column(Geometry('GEOMETRYZ', srid=4326), nullable=False)
    geom_type = Column(String, nullable=False)
    notes = Column(Text, nullable=True, comment='Примечание к элементу (связанные негеометрические объекты)')
    extra_data = Column(JSONB, nullable=True)


# Schema для файлов DXF (совместимость с существующим кодом)
class DxfFile(Base, DxfFileBase):
    """ Таблица для хранения целых DXF файлов """

    __tablename__ = 'dxf_files'
    __table_args__ = {'schema': 'file_schema'}
