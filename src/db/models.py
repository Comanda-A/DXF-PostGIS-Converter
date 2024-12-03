from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from .database import Base



class File(Base):
    ''' Таблица с файлами. '''

    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)
    file_metadata = Column(JSONB, nullable=False)
    upload_date = Column(DateTime)
    update_date = Column(DateTime)

    layers = relationship('Layer', back_populates='file', cascade='all, delete-orphan')


class Layer(Base):
    ''' Таблица со слоями. '''

    __tablename__ = 'layers'

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    name = Column(String, nullable=False)
    color = Column(String, nullable=True)
    description = Column(String, nullable=False)
    layer_metadata = Column(JSONB, nullable=False)

    file = relationship('File', back_populates='layers')
    geometric_objects = relationship('GeometricObject', back_populates='layer_relationship', cascade='all, delete-orphan')
    non_geometric_objects = relationship('NonGeometricObject', back_populates='layer', cascade='all, delete-orphan')


class NonGeometricObject(Base):
    ''' Таблица с не геом. объектами. ''' # которые не поддерживают postgis
    __tablename__ = 'non_geometric_objects'

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    layer_id = Column(Integer, ForeignKey('layers.id'), nullable=False)
    geom_type = Column(String, nullable=False)
    extra_data = Column(JSONB, nullable=False)  # просто в json

    layer = relationship('Layer', back_populates='non_geometric_objects')


class GeometricObject(Base):
    ''' Таблица с геом. объектами. ''' # которые поддерживают postgis
    __tablename__ = 'geometric_objects'

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    layer_id = Column(Integer, ForeignKey('layers.id'), nullable=False)
    geom_type = Column(String, nullable=False)
    geometry = Column(Geometry('GEOMETRYZ', srid=4326), nullable=False)  # PostGIS тип GEOMETRYZ
    extra_data = Column(JSONB, nullable=False)  # доп данные в json

    layer_relationship  = relationship('Layer', back_populates='geometric_objects')
