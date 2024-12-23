from shapely.geometry import Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon, GeometryCollection
from shapely.geometry.base import BaseGeometry
from ezdxf.entities import DXFEntity, Point as DXFPoint, Line, Polyline, LWPolyline, Circle, Arc, MultiLeader, Insert, Solid3d, Spline, Ellipse
from ezdxf.entities import MText, Solid, Face3d, Trace, Body, Region, Mesh, Hatch, Leader, Shape, Viewport, ImageDef, Image
from ezdxf.entities import Dimension, Ray, XLine, SeqEnd, Helix
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
    
    elif geom_type == 'SPLINE':
        geometry, extra_data = _convert_spline_to_postgis(entity)

    elif geom_type == 'ELLIPSE':
        geometry, extra_data = _convert_ellipse_to_postgis(entity)

    elif geom_type == 'MTEXT':
        geometry, extra_data = _convert_mtext_to_postgis(entity)

    elif geom_type == 'SOLID':
        geometry, extra_data = _convert_solid_to_postgis(entity)

    elif geom_type == 'TRACE':
        geometry, extra_data = _convert_trace_to_postgis(entity)

    elif geom_type == '3DFACE':
        geometry, extra_data = _convert_3dface_to_postgis(entity)

    elif geom_type == 'REGION':
        geometry, extra_data = _convert_region_to_postgis(entity)

    elif geom_type == 'BODY':
        geometry, extra_data = _convert_body_to_postgis(entity)

    elif geom_type == 'MESH':
        geometry, extra_data = _convert_mesh_to_postgis(entity)

    elif geom_type == 'HATCH':
        geometry, extra_data = _convert_hatch_to_postgis(entity)

    elif geom_type == 'LEADER':
        geometry, extra_data = _convert_leader_to_postgis(entity)

    elif geom_type == 'SHAPE':
        geometry, extra_data = _convert_shape_to_postgis(entity)

    elif geom_type == 'VIEWPORT':
        geometry, extra_data = _convert_viewport_to_postgis(entity)

    elif geom_type == 'IMAGE':
        geometry, extra_data = _convert_image_to_postgis(entity)

    elif geom_type == 'IMAGEDEF':
        geometry, extra_data = _convert_imagedef_to_postgis(entity)

    elif geom_type == 'DIMENSION':
        geometry, extra_data = _convert_dimension_to_postgis(entity)

    elif geom_type == 'RAY':
        geometry, extra_data = _convert_ray_to_postgis(entity)

    elif geom_type == 'XLINE':
        geometry, extra_data = _convert_xline_to_postgis(entity)

    elif geom_type == 'SEQEND':
        geometry, extra_data = _convert_seqend_to_postgis(entity)

    elif geom_type == 'HELIX':
        geometry, extra_data = _convert_helix_to_postgis(entity)

    else:
        Logger.log_error(f'dxf type = "{geom_type}" not supported')
        # raise Exception(f'dxf type = "{geom_type}" not supported")

    return geom_type, geometry, _verify_extra_data(extra_data)

def convert_postgis_to_dxf(
    file_metadata: str,
    layers: list[models.Layer],
    geom_objects: list[models.GeometricObject],
    non_geom_objects: list[models.NonGeometricObject],
    path: str
):
    # Создаем новый документ DXF
    doc = ezdxf.new()

    # Получаем заголовок документа
    header = doc.header
    
    # Добавляем данные из file_metadata в заголовок
    headers = file_metadata.get('file_metadata', {}).get('headers', {})
    for key, value in headers.items():
        if isinstance(value, list) and all(isinstance(v, (int, float)) for v in value):
            # Если значение — это список чисел (например, координаты), оставляем его как есть
            header[key] = value
        else:
            # Если значение обычное, просто добавляем его в заголовок
            header[key] = str(value)  # Преобразуем в строку только если это не список чисел
    
    # Добавляем версию в заголовок
    version = file_metadata.get('file_metadata', {}).get('version', '')
    if version:
        header['$ACADVER'] = version

    # Добавляем слои и объекты в DXF
    for layer in layers:
        # Извлекаем метаданные для текущего слоя
        layer_metadata = layer.layer_metadata

        # Проверяем, существует ли слой
        if not doc.layers.has_entry(layer.name):  
            # Создаем новый слой
            new_layer = doc.layers.new(name=layer.name)

            # Устанавливаем атрибуты для слоя из метаданных
            if 'color' in layer_metadata:
                new_layer.color = layer_metadata['color']  # Цвет слоя

            if 'lineweight' in layer_metadata:
                new_layer.lineweight = layer_metadata['lineweight']  # Вес линии

            if 'is_frozen' in layer_metadata:
                new_layer.is_frozen = layer_metadata['is_frozen']  # Замороженность слоя

            if 'is_locked' in layer_metadata:
                new_layer.is_locked = layer_metadata['is_locked']  # Заблокированность слоя

            if 'linetype' in layer_metadata:
                new_layer.linetype = layer_metadata['linetype']  # Тип линии слоя
            
            if 'is_off' in layer_metadata:
                new_layer.is_off = layer_metadata['is_off']  # Выключен ли слой


    # Добавление геометрических объектов
    for geom_object in geom_objects:
        layer_name = geom_object.layer_relationship.name
        geom_type = geom_object.geom_type

        attribs = _verify_attributes(geom_object.extra_data.get('attributes', {}))
        
        if geom_type == 'POINT':
            location = tuple(attribs['location'])
            doc.modelspace().add_point(
                location,
                dxfattribs=attribs
            )

        elif geom_type == 'LINE':
            start = tuple(attribs['start'])
            end = tuple(attribs['end'])
            doc.modelspace().add_line(start, end, dxfattribs=attribs)
            
        elif geom_type == 'POLYLINE':
            points = geom_object.extra_data['points']
            if attribs.get('is_closed', False):
                doc.modelspace().add_lwpolyline(points, dxfattribs=attribs, close=True)
            else:
                doc.modelspace().add_lwpolyline(points, dxfattribs=attribs)

        elif geom_type == 'LWPOLYLINE':
            points = [tuple(point) for point in geom_object.extra_data['points']]
            if attribs.get('is_closed', False):
                del attribs['is_closed'] # ezdxf почему то не нравится этот атрибут
                doc.modelspace().add_lwpolyline(points, dxfattribs=attribs, close=True)
            else:
                del attribs['is_closed'] # ezdxf почему то не нравится этот атрибут
                doc.modelspace().add_lwpolyline(points, dxfattribs=attribs)

        elif geom_type == 'CIRCLE':
            center = tuple(attribs['center'])
            radius = attribs['radius']
            doc.modelspace().add_circle(center, radius, dxfattribs=attribs)

        elif geom_type == 'ARC':
            center = tuple(attribs['center'])
            radius = attribs['radius']
            start_angle = attribs['start_angle']
            end_angle = attribs['end_angle']
            doc.modelspace().add_arc(center, radius, start_angle, end_angle, dxfattribs=attribs)

        elif geom_type == 'MULTILEADER':
            base_point = attribs.get('base_point', (0, 0, 0))
            text = geom_object.extra_data.get('text', "")
            doc.modelspace().add_mtext(text).set_location(base_point)

        elif geom_type == 'INSERT':
            insertion_point = tuple(attribs['insert'])
            block_name = geom_object.extra_data['block_name']
            doc.modelspace().add_blockref(block_name, insertion_point, dxfattribs=attribs)

        else:
            Logger.log_error(f'postgis to dxf. dxf type = "{geom_type}" not supported.')

    # Добавление негеометрических объектов
    for non_geom_object in non_geom_objects:
        layer_name = non_geom_object.layer.name
        geom_type = non_geom_object.geom_type
        
        attribs = _verify_attributes(non_geom_object.extra_data.get('attributes', {}))

        # Пример добавления текстового объекта
        if geom_type == 'TEXT':
            text = attribs['text']
            location = tuple(attribs['insert'])
            height=attribs['height'] if 'height' in attribs else 0
            rotation=attribs['rotation'] if 'rotation' in attribs else 0
            doc.modelspace().add_text(text, height=height, rotation=rotation, dxfattribs=attribs)

        elif geom_type == '3DSOLID':
            try:
                # Получаем ACIS данные из extra_data
                acis_data = non_geom_object.extra_data.get('acis_data', None)
                if not acis_data:
                    raise ValueError("ACIS data is missing")
                
                # Создаем объект Solid3d
                entity = doc.modelspace().add_3dsolid(attribs)
                
                # Устанавливаем ACIS данные в объект Solid3d
                entity.sat = acis_data
            except Exception as e:
                Logger.log_error("convert_postgis_to_dxf() geom_type == '3DSOLID' ERROR. e: " + str(e))
            
    # Сохраняем DXF файл
    doc.saveas(path)


def _verify_attributes(attributes: dict) -> dict:
    """
    атрибуты из dict переводим в типы понятные ezdxf
    """
    attribs = {}

    for key, value in attributes.items():
        # Проверяем и добавляем атрибуты, если они имеют корректные значения
        if key in ['location', 'insert']:
            attribs[key] = tuple(value)  # Преобразуем список в кортеж

        elif key in ['ltscale', 'linetype', 'invisible', 'lineweight', 'true_color'] and isinstance(value, list):
            attribs[key] = value[0]  # Берем первый элемент, если это список

        elif value is not None:
            attribs[key] = value
    
    return attribs


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
    
def _convert_text_to_postgis(entity: Text) -> tuple[BaseGeometry, dict]:
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

def _convert_spline_to_postgis(entity: Spline) -> tuple[BaseGeometry, dict]:
    '''SPLINE в DXF представляет собой кривую Безье или Б-сплайн. В Shapely нет прямого эквивалента, но можно аппроксимировать кривую точками.'''
    points = [tuple(v) for v in entity.flattening(0.01)]
    extra_data = _attributes_to_dict(entity)
    extra_data['points'] = points
    return LineString(points), extra_data

def _convert_ellipse_to_postgis(entity: Ellipse) -> tuple[BaseGeometry, dict]:
    '''ELLIPSE в DXF представляет собой эллипс. В Shapely можно аппроксимировать эллипс точками.'''
    center = (entity.dxf.center.x, entity.dxf.center.y, entity.dxf.center.z)
    major_axis = (entity.dxf.major_axis.x, entity.dxf.major_axis.y, entity.dxf.major_axis.z)
    ratio = entity.dxf.axis_ratio
    start_param = entity.dxf.start_param
    end_param = entity.dxf.end_param

    # Создаем точки для аппроксимации эллипса
    angles = np.linspace(start_param, end_param, 100)
    ellipse_points = [
        (
            center[0] + major_axis[0] * np.cos(angle) * ratio,
            center[1] + major_axis[1] * np.sin(angle),
            center[2]
        )
        for angle in angles
    ]

    extra_data = _attributes_to_dict(entity)
    return LineString(ellipse_points), extra_data

def _convert_mtext_to_postgis(entity: MText) -> tuple[BaseGeometry, dict]:
    '''MTEXT в DXF представляет собой многострочный текст. В Shapely нет прямого эквивалента, но можно сохранить текст и его позицию.'''
    extra_data = _attributes_to_dict(entity)
    extra_data['text'] = entity.text
    return None, extra_data

def _convert_solid_to_postgis(entity: Solid) -> tuple[BaseGeometry, dict]:
    '''`SOLID` в DXF представляет собой четырехугольник. В Shapely можно представить его как `Polygon`.'''
    points = [
        (entity.dxf.vtx0.x, entity.dxf.vtx0.y, entity.dxf.vtx0.z),
        (entity.dxf.vtx1.x, entity.dxf.vtx1.y, entity.dxf.vtx1.z),
        (entity.dxf.vtx2.x, entity.dxf.vtx2.y, entity.dxf.vtx2.z),
        (entity.dxf.vtx3.x, entity.dxf.vtx3.y, entity.dxf.vtx3.z)
    ]
    extra_data = _attributes_to_dict(entity)
    extra_data['points'] = points
    return Polygon(points), extra_data

def _convert_trace_to_postgis(entity: Trace) -> tuple[BaseGeometry, dict]:
    '''`TRACE` в DXF также представляет собой четырехугольник. Обработка аналогична `SOLID`.'''
    points = [
        (entity.dxf.vtx0.x, entity.dxf.vtx0.y, entity.dxf.vtx0.z),
        (entity.dxf.vtx1.x, entity.dxf.vtx1.y, entity.dxf.vtx1.z),
        (entity.dxf.vtx2.x, entity.dxf.vtx2.y, entity.dxf.vtx2.z),
        (entity.dxf.vtx3.x, entity.dxf.vtx3.y, entity.dxf.vtx3.z)
    ]
    extra_data = _attributes_to_dict(entity)
    extra_data['points'] = points
    return Polygon(points), extra_data

def _convert_3dface_to_postgis(entity: Face3d) -> tuple[BaseGeometry, dict]:
    '''`3DFACE` в DXF представляет собой треугольник или четырехугольник. В Shapely можно представить его как `Polygon`.'''
    points = [
        (entity.dxf.vtx0.x, entity.dxf.vtx0.y, entity.dxf.vtx0.z),
        (entity.dxf.vtx1.x, entity.dxf.vtx1.y, entity.dxf.vtx1.z),
        (entity.dxf.vtx2.x, entity.dxf.vtx2.y, entity.dxf.vtx2.z),
        (entity.dxf.vtx3.x, entity.dxf.vtx3.y, entity.dxf.vtx3.z)
    ]
    # Если четвертая вершина совпадает с первой, это треугольник
    if points[0] == points[3]:
        points.pop()
    extra_data = _attributes_to_dict(entity)
    extra_data['points'] = points
    return Polygon(points), extra_data

def _convert_region_to_postgis(entity: Region) -> tuple[BaseGeometry, dict]:
    '''`REGION` в DXF представляет собой трехмерный регион. В Shapely нет прямого эквивалента, но можно сохранить ACIS данные.'''
    try:
        acis_data = entity.acis_data
    except Exception as e:
        Logger.log_error("_convert_region_to_postgis() ERROR. e: " + str(e))
        return None, {}

    extra_data = _attributes_to_dict(entity)
    extra_data['acis_data'] = acis_data

    return None, extra_data

def _convert_body_to_postgis(entity: Body) -> tuple[BaseGeometry, dict]:
    '''`BODY` в DXF представляет собой трехмерное тело. В Shapely нет прямого эквивалента, но можно сохранить ACIS данные.'''
    try:
        acis_data = entity.acis_data
    except Exception as e:
        Logger.log_error("_convert_body_to_postgis() ERROR. e: " + str(e))
        return None, {}

    extra_data = _attributes_to_dict(entity)
    extra_data['acis_data'] = acis_data

    return None, extra_data

def _convert_mesh_to_postgis(entity: Mesh) -> tuple[BaseGeometry, dict]:
    '''`MESH` в DXF представляет собой сетку. В Shapely нет прямого эквивалента, но можно сохранить вершины и грани.'''
    vertices = [tuple(v) for v in entity.vertices()]
    faces = [tuple(f) for f in entity.faces()]
    extra_data = _attributes_to_dict(entity)
    extra_data['vertices'] = vertices
    extra_data['faces'] = faces
    return None, extra_data

def _convert_hatch_to_postgis(entity: Hatch) -> tuple[BaseGeometry, dict]:
    '''`HATCH` в DXF представляет собой заливку. В Shapely можно представить его как `Polygon`.'''
    polygons = []
    for boundary in entity.paths:
        points = [tuple(v) for v in boundary.vertices()]
        polygons.append(Polygon(points))
    extra_data = _attributes_to_dict(entity)
    if len(polygons) == 1:
        return polygons[0], extra_data
    else:
        return MultiPolygon(polygons), extra_data

def _convert_leader_to_postgis(entity: Leader) -> tuple[BaseGeometry, dict]:
    '''`LEADER` в DXF представляет собой линию с текстом. В Shapely можно представить его как `LineString` и сохранить текст.'''
    points = [tuple(v) for v in entity.vertices()]
    extra_data = _attributes_to_dict(entity)
    extra_data['text'] = entity.dxf.text
    return LineString(points), extra_data

'''
def _convert_ellipsearc_to_postgis(entity: EllipseArc) -> tuple[BaseGeometry, dict]:
    #`ELLIPSEARC` в DXF представляет собой дугу эллипса. В Shapely можно аппроксимировать дугу точками.
    center = (entity.dxf.center.x, entity.dxf.center.y, entity.dxf.center.z)
    major_axis = (entity.dxf.major_axis.x, entity.dxf.major_axis.y, entity.dxf.major_axis.z)
    ratio = entity.dxf.axis_ratio
    start_param = entity.dxf.start_param
    end_param = entity.dxf.end_param

    # Создаем точки для аппроксимации дуги эллипса
    angles = np.linspace(start_param, end_param, 100)
    ellipsearc_points = [
        (
            center[0] + major_axis[0] * np.cos(angle) * ratio,
            center[1] + major_axis[1] * np.sin(angle),
            center[2]
        )
        for angle in angles
    ]

    extra_data = _attributes_to_dict(entity)
    return LineString(ellipsearc_points), extra_data
'''

def _convert_shape_to_postgis(entity: Shape) -> tuple[BaseGeometry, dict]:
    '''`SHAPE` в DXF представляет собой встроенный двумерный объект. В Shapely нет прямого эквивалента, но можно сохранить данные о блоке.'''
    insertion_point = (entity.dxf.insert.x, entity.dxf.insert.y, entity.dxf.insert.z)
    block_name = entity.dxf.name
    extra_data = _attributes_to_dict(entity)
    extra_data['block_name'] = block_name
    return Point(insertion_point), extra_data

def _convert_viewport_to_postgis(entity: Viewport) -> tuple[BaseGeometry, dict]:
    '''`VIEWPORT` в DXF представляет собой область просмотра. В Shapely нет прямого эквивалента, но можно сохранить данные о области.'''
    center = (entity.dxf.center.x, entity.dxf.center.y, entity.dxf.center.z)
    width = entity.dxf.width
    height = entity.dxf.height
    extra_data = _attributes_to_dict(entity)
    extra_data['width'] = width
    extra_data['height'] = height
    return Point(center), extra_data

def _convert_image_to_postgis(entity: Image) -> tuple[BaseGeometry, dict]:
    '''`IMAGE` в DXF представляет собой изображение. В Shapely нет прямого эквивалента, но можно сохранить данные о изображении.'''
    insertion_point = (entity.dxf.insert.x, entity.dxf.insert.y, entity.dxf.insert.z)
    u_size = entity.dxf.u_size
    v_size = entity.dxf.v_size
    image_def_handle = entity.dxf.image_def_handle
    extra_data = _attributes_to_dict(entity)
    extra_data['insertion_point'] = insertion_point
    extra_data['u_size'] = u_size
    extra_data['v_size'] = v_size
    extra_data['image_def_handle'] = image_def_handle
    return Point(insertion_point), extra_data

def _convert_imagedef_to_postgis(entity: ImageDef) -> tuple[BaseGeometry, dict]:
    '''`IMAGEDEF` в DXF представляет собой определение изображения. В Shapely нет прямого эквивалента, но можно сохранить данные о изображении.'''
    filename = entity.dxf.filename
    extra_data = _attributes_to_dict(entity)
    extra_data['filename'] = filename
    return None, extra_data

def _convert_dimension_to_postgis(entity: Dimension) -> tuple[BaseGeometry, dict]:
    '''`DIMENSION` в DXF представляет собой измерение. В Shapely нет прямого эквивалента, но можно сохранить данные об измерении.'''
    extra_data = _attributes_to_dict(entity)
    return None, extra_data

def _convert_ray_to_postgis(entity: Ray) -> tuple[BaseGeometry, dict]:
    '''`RAY` в DXF представляет собой луч. В Shapely нет прямого эквивалента, но можно сохранить данные о луче.'''
    start_point = (entity.dxf.start.x, entity.dxf.start.y, entity.dxf.start.z)
    unit_vector = (entity.dxf.unit_vector.x, entity.dxf.unit_vector.y, entity.dxf.unit_vector.z)
    extra_data = _attributes_to_dict(entity)
    extra_data['start_point'] = start_point
    extra_data['unit_vector'] = unit_vector
    return Point(start_point), extra_data

def _convert_xline_to_postgis(entity: XLine) -> tuple[BaseGeometry, dict]:
    '''`XLINE` в DXF представляет собой бесконечную линию. В Shapely нет прямого эквивалента, но можно сохранить данные о линии.'''
    start_point = (entity.dxf.start.x, entity.dxf.start.y, entity.dxf.start.z)
    unit_vector = (entity.dxf.unit_vector.x, entity.dxf.unit_vector.y, entity.dxf.unit_vector.z)
    extra_data = _attributes_to_dict(entity)
    extra_data['start_point'] = start_point
    extra_data['unit_vector'] = unit_vector
    return Point(start_point), extra_data

'''
def _convert_vertex_to_postgis(entity: Vertex) -> tuple[BaseGeometry, dict]:
    #`VERTEX` в DXF представляет собой вершину. В Shapely нет прямого эквивалента, но можно сохранить данные о вершине.
    location = (entity.dxf.location.x, entity.dxf.location.y, entity.dxf.location.z)
    extra_data = _attributes_to_dict(entity)
    extra_data['location'] = location
    return Point(location), extra_data
'''

def _convert_seqend_to_postgis(entity: SeqEnd) -> tuple[BaseGeometry, dict]:
    '''`SEQEND` в DXF представляет собой конец последовательности. В Shapely нет прямого эквивалента, но можно сохранить данные о последовательности.'''
    extra_data = _attributes_to_dict(entity)
    return None, extra_data

'''
def _convert_3dpoint_to_postgis(entity: Point3D) -> tuple[BaseGeometry, dict]:
    #`3DPOINT` в DXF представляет собой трехмерную точку. В Shapely это можно представить как `Point`.
    location = (entity.dxf.location.x, entity.dxf.location.y, entity.dxf.location.z)
    extra_data = _attributes_to_dict(entity)
    extra_data['location'] = location
    return Point(location), extra_data
'''

def _convert_helix_to_postgis(entity: Helix) -> tuple[BaseGeometry, dict]:
    '''HELIX в DXF представляет собой спираль. В Shapely можно аппроксимировать спираль точками.'''
    base_point = (entity.dxf.base_point.x, entity.dxf.base_point.y, entity.dxf.base_point.z)
    axis_vector = (entity.dxf.axis_vector.x, entity.dxf.axis_vector.y, entity.dxf.axis_vector.z)
    radius = entity.dxf.radius
    turns = entity.dxf.turns
    height = entity.dxf.height

    # Создаем точки для аппроксимации спирали
    angles = np.linspace(0, 2 * np.pi * turns, 100)
    helix_points = [
        (
            base_point[0] + radius * np.cos(angle),
            base_point[1] + radius * np.sin(angle),
            base_point[2] + (angle / (2 * np.pi * turns)) * height
        )
        for angle in angles
    ]

    extra_data = _attributes_to_dict(entity)
    return LineString(helix_points), extra_data
