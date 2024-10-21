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

    file = relationship('File', back_populates='layers')
    geometric_objects = relationship('GeometricObject', back_populates='layer_relationship', cascade='all, delete-orphan')
    non_geometric_objects = relationship('NonGeometricObject', back_populates='layer', cascade='all, delete-orphan')


class NonGeometricObject(Base):
    ''' Таблица с не геом. объектами. ''' # которые не поддерживают postgis
    __tablename__ = 'non_geometric_objects'

    id = Column(Integer, primary_key=True)
    layer_id = Column(Integer, ForeignKey('layers.id'), nullable=False)
    geom_type = Column(String, nullable=False)
    geometry = Column(JSONB, nullable=False)  # просто в json

    layer = relationship('Layer', back_populates='non_geometric_objects')


class GeometricObject(Base):
    ''' Таблица с геом. объектами. ''' # которые поддерживают postgis
    __tablename__ = 'geometric_objects'

    id = Column(Integer, primary_key=True)
    layer_id = Column(Integer, ForeignKey('layers.id'), nullable=False)
    geom_type = Column(String, nullable=False)
    geometry = Column(Geometry('GEOMETRYZ', srid=4326), nullable=False)  # PostGIS тип GEOMETRYZ

    layer_relationship  = relationship('Layer', back_populates='geometric_objects')
    geometry_relationship  = relationship('Geometry', back_populates='geometric_object')
    attribute_relationship  = relationship('Attribute', back_populates='geometric_object')


class Geometry(Base):
    ''' Таблица с геометрией объектов. '''
    __tablename__ = 'geometries'

    id = Column(Integer, primary_key=True)
    object_id = Column(Integer, ForeignKey('geometric_objects.id'), nullable=False)
    value = Column(JSONB, nullable=False)

    geometric_object = relationship('GeometricObject', back_populates='geometry_relationship')


class Attribute(Base):
    ''' Таблица с атибутами объектов. '''
    __tablename__ = 'attributes'

    id = Column(Integer, primary_key=True)
    object_id = Column(Integer, ForeignKey('geometric_objects.id'), nullable=False)
    value = Column(JSONB, nullable=False)

    geometric_object = relationship('GeometricObject', back_populates='attribute_relationship')
