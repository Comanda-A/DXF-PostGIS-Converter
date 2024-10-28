from shapely.geometry import Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon, GeometryCollection
from shapely.geometry.base import BaseGeometry
from ezdxf.entities import DXFEntity, Point as DXFPoint, Line, Polyline, LWPolyline, Circle, Arc, MultiLeader, Insert, Solid3d
from ezdxf.entities.text import Text
from ezdxf.math import Vec3
from . import models
import math
import ezdxf
import numpy as np

from ..logger.logger import Logger


def convert_dxf_to_postgis(entity: DXFEntity) -> tuple[str, BaseGeometry, dict]:
    geom_type = entity.dxftype()
    geometry = None
    extra_data = {}

    if geom_type == 'POINT':
        geometry, extra_data = _convert_point_to_postgis(entity)

    elif geom_type == 'LINE':
        geometry, extra_data = _convert_line_to_postgis(entity)
        
    elif geom_type == 'POLYLINE':
        geometry, extra_data = _convert_polyline_to_postgis(entity)

    elif geom_type == 'LWPOLYLINE':
        geometry, extra_data = _convert_lwpolyline_to_postgis(entity)

    elif geom_type == 'TEXT':
        geometry, extra_data = _convert_text_to_postgis(entity)
    
    elif geom_type == 'CIRCLE':
        geometry, extra_data = _convert_circle_to_postgis(entity)

    elif geom_type == 'ARC':
        geometry, extra_data = _convert_arc_to_postgis(entity)

    elif geom_type == 'MULTILEADER':
        geometry, extra_data = _convert_multileader_to_postgis(entity)

    elif geom_type == 'INSERT':
        geometry, extra_data = _convert_insert_to_postgis(entity)

    elif geom_type == '3DSOLID':
        geometry, extra_data = _convert_3dsolid_to_postgis(entity)

    else:
        Logger.log_error(f'dxf type = "{geom_type}" not supported')
        # raise Exception(f'dxf type = "{geom_type}" not supported")

    return geom_type, geometry, _verify_extra_data(extra_data)


def convert_postgis_to_dxf(
    layers: list[models.Layer],
    geom_objects: list[models.GeometricObject],
    non_geom_objects: list[models.NonGeometricObject],
    path: str
):
    # Создаем новый документ DXF
    doc = ezdxf.new()

    # Добавляем слои и объекты в DXF
    for layer in layers:
        doc.layers.new(name=layer.name)

    # Добавление геометрических объектов
    for geom_object in geom_objects:
        layer_name = geom_object.layer_relationship.name
        geom_type = geom_object.geom_type
        attributes = geom_object.extra_data.get('attributes', {})
        attribs = {}

        # Проверяем и добавляем атрибуты, если они имеют корректные значения
        if "color" in attributes and attributes["color"] is not None:
            attribs["color"] = attributes["color"]

        if "layer" in attributes and attributes["layer"] is not None:
            attribs["layer"] = attributes["layer"]

        if "location" in attributes and isinstance(attributes["location"], list) and len(attributes["location"]) >= 3:
            attribs["location"] = tuple(attributes["location"])  # Преобразуем список в кортеж

        if "ltscale" in attributes and isinstance(attributes["ltscale"], list) and attributes["ltscale"]:
            attribs["ltscale"] = attributes["ltscale"][0]  # Берем первый элемент, если это список

        if "linetype" in attributes and isinstance(attributes["linetype"], list) and attributes["linetype"]:
            attribs["linetype"] = attributes["linetype"][0]  # Берем первый элемент, если это список

        if "invisible" in attributes and isinstance(attributes["invisible"], list) and attributes["invisible"]:
            attribs["invisible"] = attributes["invisible"][0]  # Берем первый элемент, если это список

        if "lineweight" in attributes and isinstance(attributes["lineweight"], list) and attributes["lineweight"]:
            attribs["lineweight"] = attributes["lineweight"][0]  # Берем первый элемент, если это список

        if "true_color" in attributes and isinstance(attributes["true_color"], list) and attributes["true_color"]:
            attribs["true_color"] = attributes["true_color"][0]  # Берем первый элемент, если это список

        if "transparency" in attributes and attributes["transparency"] is not None:
            attribs["transparency"] = attributes["transparency"]
        
        if geom_type == 'POINT':
            location = tuple(geom_object.extra_data['attributes']['location'])
            doc.modelspace().add_point(
                location,
                dxfattribs=attribs
            )

        elif geom_type == 'LINE':
            start = tuple(geom_object.extra_data['attributes']['start'])
            end = tuple(geom_object.extra_data['attributes']['end'])
            doc.modelspace().add_line(start, end, dxfattribs=attribs)
            
        elif geom_type == 'POLYLINE':
            points = geom_object.extra_data['points']
            if geom_object.extra_data['attributes'].get('is_closed', False):
                doc.modelspace().add_lwpolyline(points, dxfattribs=attribs, close=True)
            else:
                doc.modelspace().add_lwpolyline(points, dxfattribs=attribs)

        elif geom_type == 'LWPOLYLINE':
            points = [tuple(point) for point in geom_object.extra_data['points']] 
            if geom_object.extra_data['attributes'].get('is_closed', False):
                doc.modelspace().add_lwpolyline(points, dxfattribs=attribs, close=True)
            else:
                doc.modelspace().add_lwpolyline(points, dxfattribs=attribs)

        elif geom_type == 'CIRCLE':
            center = tuple(geom_object.extra_data['attributes']['center'])
            radius = geom_object.extra_data['attributes']['radius']
            doc.modelspace().add_circle(center, radius, dxfattribs=attribs)

        elif geom_type == 'ARC':
            center = tuple(geom_object.extra_data['attributes']['center'])
            radius = geom_object.extra_data['attributes']['radius']
            start_angle = geom_object.extra_data['attributes']['start_angle']
            end_angle = geom_object.extra_data['attributes']['end_angle']
            doc.modelspace().add_arc(center, radius, start_angle, end_angle, dxfattribs=attribs)

        elif geom_type == 'MULTILEADER':
            base_point = geom_object.extra_data['attributes'].get('base_point', (0, 0, 0))
            text = geom_object.extra_data.get('text', "")
            doc.modelspace().add_mtext(text).set_location(base_point)

        elif geom_type == 'INSERT':
            insertion_point = tuple(geom_object.extra_data['attributes']['insert'])
            block_name = geom_object.extra_data['block_name']
            doc.modelspace().add_blockref(block_name, insertion_point, dxfattribs=attribs)

        elif geom_type == '3DSOLID':
            pass  # Для 3D SOLID потребуется экспортировать или обработать ACIS данные

        else:
            Logger.log_error(f'postgis to dxf. dxf type = "{geom_type}" not supported.')

    # Добавление негеометрических объектов
    for non_geom_object in non_geom_objects:
        layer_name = non_geom_object.layer.name
        geom_type = non_geom_object.geom_type

        # Пример добавления текстового объекта
        if geom_type == 'TEXT':
            text = non_geom_object.extra_data['attributes']['text']
            location = tuple(non_geom_object.extra_data['attributes']['insert'])
            doc.modelspace().add_text(text, dxfattribs={'layer': layer_name})
            

    # Сохраняем DXF файл
    doc.saveas(path)


def _replace_vec3_to_list(data):
    if isinstance(data, dict):
        return {key: _replace_vec3_to_list(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_replace_vec3_to_list(item) for item in data]
    elif isinstance(data, Vec3):
        return [data.x, data.y, data.z]
    else:
        return data

def _verify_extra_data(data):
    data = _replace_vec3_to_list(data)
    return data

def _attributes_to_dict(entity: DXFEntity, data: dict = None) -> dict:
    if data is None:
        data = {}

    if 'attributes' not in data or not isinstance(data['attributes'], dict):
        data['attributes'] = {}
    
    for key, value in entity.dxfattribs().items():
        data['attributes'][key] = value

    data['attributes']['color'] = entity.dxf.color
    data['attributes']['linetype'] = entity.dxf.linetype,
    data['attributes']['lineweight'] = entity.dxf.lineweight,
    data['attributes']['ltscale'] = entity.dxf.ltscale,
    data['attributes']['invisible'] = entity.dxf.invisible,
    data['attributes']['true_color'] = entity.dxf.true_color,
    data['attributes']['transparency'] = entity.dxf.transparency

    return data
    

def _convert_point_to_postgis(entity: DXFPoint) -> tuple[BaseGeometry, dict]:
    extra_data = _attributes_to_dict(entity)
    return Point(entity.dxf.location.x, entity.dxf.location.y, entity.dxf.location.z), extra_data


def _convert_line_to_postgis(entity: Line) -> tuple[BaseGeometry, dict]:
    extra_data = _attributes_to_dict(entity)

    start = (entity.dxf.start.x, entity.dxf.start.y, entity.dxf.start.z)
    end = (entity.dxf.end.x, entity.dxf.end.y, entity.dxf.end.z)
    return LineString([start, end]), extra_data


def _convert_polyline_to_postgis(entity: Polyline) -> tuple[BaseGeometry, dict]:
    points = [(v.x, v.y, v.z) for v in entity.points()]
    
    extra_data = _attributes_to_dict(entity)
    extra_data['points'] = points
    extra_data['attributes']['is_closed'] = entity.is_closed
    
    if entity.is_closed:
        return Polygon(points), extra_data
    else:
        return LineString(points), extra_data
    

def _convert_lwpolyline_to_postgis(entity: LWPolyline) -> tuple[BaseGeometry, dict]:
    points = [(v.x, v.y, v.z) for v in entity.vertices_in_ocs()]
    
    extra_data = _attributes_to_dict(entity)
    extra_data['points'] = points
    extra_data['attributes']['is_closed'] = entity.is_closed
    
    if entity.is_closed:
        return Polygon(points), extra_data
    else:
        return LineString(points), extra_data
    

def _convert_text_to_postgis(entity: LWPolyline) -> tuple[BaseGeometry, dict]:
    extra_data = _attributes_to_dict(entity)
    return None, extra_data


def _convert_circle_to_postgis(entity: Circle) -> tuple[BaseGeometry, dict]:
    center = (entity.dxf.center.x, entity.dxf.center.y, entity.dxf.center.z)
    radius = entity.dxf.radius

    # Создаем 100 точек для круга
    angles = np.linspace(0, 2 * np.pi, 100)
    circle_points = [
        (center[0] + radius * np.cos(angle), center[1] + radius * np.sin(angle), center[2])
        for angle in angles
    ]

    # Создаем многоугольник из точек
    circle = Polygon(circle_points)  # Используем Polygon для создания круга с Z

    extra_data = _attributes_to_dict(entity)
    return circle, extra_data


def _convert_arc_to_postgis(entity: Arc) -> tuple[BaseGeometry, dict]:
    center = (entity.dxf.center.x, entity.dxf.center.y, entity.dxf.center.z)  # Убедитесь, что Z-координаты присутствуют
    radius = entity.dxf.radius  # Получение радиуса
    angle_start = entity.dxf.start_angle
    angle_end = entity.dxf.end_angle

    # Для создания дуги используйте buffer на точке
    arc = Point(center).buffer(radius, resolution=100).boundary  # Создаем окружность и берем ее границу
    arc = arc.parallel_offset(-radius, side='right')  # Двигаем границу на радиус для получения дуги

    # Примените фильтрацию по углу, чтобы получить нужный отрезок
    arc = arc.intersection(LineString([
        (center[0] + radius * np.cos(np.radians(angle_start)), center[1] + radius * np.sin(np.radians(angle_start)), center[2]),
        (center[0] + radius * np.cos(np.radians(angle_end)), center[1] + radius * np.sin(np.radians(angle_end)), center[2])
    ]))

    extra_data = _attributes_to_dict(entity)
    return arc, extra_data

def _convert_multileader_to_postgis(entity: MultiLeader) -> tuple[Polygon | Point, dict]:
    geometry = None
    extra_data = _attributes_to_dict(entity)
    
    if entity.dxf.content_type == 2 and entity.context.mtext:
        # MULTILEADER с контентом MTEXT
        mtext_content = entity.context.mtext.default_content
        extra_data['text'] = mtext_content

        # Получаем точку вставки текста
        base_point = entity.context.base_point
        geometry = Point(base_point.x, base_point.y, base_point.z)

    elif entity.dxf.content_type == 1 and entity.context.block:
        # MULTILEADER с контентом BLOCK
        block_attributes = entity.get_block_content()
        extra_data['block_attributes'] = block_attributes

        # Получаем точку вставки блока
        base_point = entity.context.base_point
        geometry = Point(base_point.x, base_point.y, base_point.z)

    return geometry, extra_data

def _convert_insert_to_postgis(entity: Insert) -> tuple[BaseGeometry, dict]:
    insertion_point = (entity.dxf.insert.x, entity.dxf.insert.y, entity.dxf.insert.z)

    # Получаем имя блока
    block_name = entity.dxf.name

    extra_data = _attributes_to_dict(entity)
    extra_data['block_name'] = block_name

    # Возвращаем точку как представление вставки
    return Point(insertion_point), extra_data  # Используем точку как геометрию, можно изменить на нужный тип

def _convert_3dsolid_to_postgis(entity: Solid3d) -> tuple[Point, dict]:
    try:
        # Экспорт данных ACIS из объекта 3DSOLID
        acis_data = entity.acis_data  # Получаем двоичные данные ACIS
    except Exception as e:
        Logger.log_error("_convert_3dsolid_to_postgis() ERROR. e: " + str(e))
        return None, {}
    
    # Собираем дополнительные данные, такие как объем, если он доступен
    extra_data = _attributes_to_dict(entity)
    extra_data['acis_data'] = acis_data

    return None, extra_data