# -*- coding: utf-8 -*-
"""
PostGIS Converter - конвертация DXF сущностей в PostGIS формат.

Преобразует DXF сущности (POINT, LINE, POLYLINE и т.д.) в WKTElement объекты для 
хранения в PostgreSQL/PostGIS. Использует метод максимальной схожести для преобразования 
всех возможных типов геометрии.
"""

from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
from shapely.geometry.base import BaseGeometry
from geoalchemy2 import WKTElement

from ....domain.value_objects import Result
from ....domain.entities import DXFEntity


class PostGISEntityConverter:
    """
    Конвертер DXF сущностей в формат PostGIS.
    
    Преобразует различные типы DXF сущностей (POINT, LINE, POLYLINE,
    CIRCLE, ARC, MULTILEADER и т.д.) в WKTElement объекты для
    хранения в PostgreSQL/PostGIS с использованием SRID 4326.
    """
    
    _CONVERSION_FUNCTIONS = {
        '3DFACE': '_convert_3dface',
        '3DSOLID': '_convert_3dsolid',
        'ACAD_PROXY_ENTITY': '_convert_acad_proxy_entity',
        'ARC': '_convert_arc',
        'ATTRIB': '_convert_attrib',
        'BODY': '_convert_body',
        'CIRCLE': '_convert_circle',
        'DIMENSION': '_convert_dimension',
        'ARC_DIMENSION': '_convert_dimension',
        'ELLIPSE': '_convert_ellipse',
        'HATCH': '_convert_hatch',
        'HELIX': '_convert_helix',
        'IMAGE': '_convert_image',
        'INSERT': '_convert_insert',
        'LEADER': '_convert_leader',
        'LINE': '_convert_line',
        'LWPOLYLINE': '_convert_lwpolyline',
        'MLINE': '_convert_mline',
        'MESH': '_convert_mesh',
        'MPOLYGON': '_convert_mpolygon',
        'MTEXT': '_convert_mtext',
        'MULTILEADER': '_convert_multileader',
        'POINT': '_convert_point',
        'POLYLINE': '_convert_polyline',
        'VERTEX': '_convert_vertex',
        'POLYMESH': '_convert_polymesh',
        'POLYFACE': '_convert_polyface',
        'RAY': '_convert_ray',
        'REGION': '_convert_region',
        'SHAPE': '_convert_shape',
        'SOLID': '_convert_solid',
        'SPLINE': '_convert_spline',
        'SURFACE': '_convert_surface',
        'TEXT': '_convert_text',
        'TRACE': '_convert_trace',
        'UNDERLAY': '_convert_underlay',
        'VIEWPORT': '_convert_viewport',
        'WIPEOUT': '_convert_wipeout',
        'XLINE': '_convert_xline',
        'IMAGEDEF': '_convert_imagedef'
    }

    def to_db(self, entity: DXFEntity) -> Result[Tuple[Optional[str], Dict[str, Any]]]:
        """
        Конвертирует DXF сущность в WKT строку и дополнительные данные для БД.
        
        Args:
            entity: DXFEntity объект с геометрией и атрибутами
            
        Returns:
            Result с кортежем (wkt_string, extra_data) или ошибка
        """
        convert_func_name = self._CONVERSION_FUNCTIONS.get(entity.entity_type.value)
        if not convert_func_name:
            return Result.fail(f"Unsupported entity type: {entity.entity_type}")

        convert_func = getattr(self, convert_func_name)
        result = convert_func(entity)
        
        if not result.is_success:
            return result

        geometry, extra_data = result.value
        
        # Если нет геометрии, возвращаем None и extra_data
        if geometry is None:
            return Result.success((None, extra_data))

        # Если geometry уже строка (WKT)
        if isinstance(geometry, str):
            return Result.success((geometry, extra_data))

        # Конвертируем Shapely объект в WKT строку
        try:
            wkt_str = geometry.wkt
            return Result.success((wkt_str, extra_data))
        except AttributeError:
            return Result.fail(
                f"Conversion error for {entity.entity_type}: "
                f"Expected Shapely object, got {type(geometry).__name__}"
            )

    def from_db(self, data: Dict[str, Any]) -> Result[DXFEntity]:
        """Конвертирует данные из БД обратно в DXFEntity"""
        # TODO: Реализовать обратную конвертацию
        pass

    # ========== Helper Methods ==========

    def _extract_point(self, point_data) -> Tuple[float, float, float]:
        """
        Извлекает координаты из различных форматов точек.
        Поддерживает списки, кортежи и словари.
        """
        if isinstance(point_data, (list, tuple)):
            if len(point_data) >= 3:
                return (float(point_data[0]), float(point_data[1]), float(point_data[2]))
            elif len(point_data) == 2:
                return (float(point_data[0]), float(point_data[1]), 0.0)
        elif isinstance(point_data, dict):
            return (
                float(point_data.get('x', 0)),
                float(point_data.get('y', 0)),
                float(point_data.get('z', 0))
            )
        return (0.0, 0.0, 0.0)

    def _build_extra_data(self, entity: DXFEntity, additional_data: Dict = None) -> Dict[str, Any]:
        """Формирует словарь с дополнительными данными сущности"""
        extra_data = {
            'attributes': entity.attributes.copy(),
            'entity_type': entity.entity_type.value,
            'name': entity.name
        }
        if additional_data:
            extra_data.update(additional_data)
        if entity.extra_data:
            extra_data['extra'] = entity.extra_data
        return extra_data

    def _get_geometry_value(self, entity: DXFEntity, key: str, default=None):
        """Безопасное получение значения из geometries"""
        return entity.geometries.get(key, default)

    def _get_attribute_value(self, entity: DXFEntity, key: str, default=None):
        """Безопасное получение значения из attributes"""
        return entity.attributes.get(key, default)

    # ========== Point Converters ==========

    def _convert_point(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация POINT"""
        location = self._get_geometry_value(entity, 'location')
        if not location:
            return Result.fail("POINT: missing location")
        
        point = self._extract_point(location)
        extra_data = self._build_extra_data(entity)
        
        return Result.success((Point(*point), extra_data))

    # ========== Line Converters ==========

    def _convert_line(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация LINE"""
        start = self._get_geometry_value(entity, 'start')
        end = self._get_geometry_value(entity, 'end')
        
        if not start or not end:
            return Result.fail("LINE: missing start or end point")
        
        start_point = self._extract_point(start)
        end_point = self._extract_point(end)
        
        extra_data = self._build_extra_data(entity)
        
        return Result.success((LineString([start_point, end_point]), extra_data))

    def _convert_ray(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация RAY"""
        start = self._get_geometry_value(entity, 'start')
        unit_vector = self._get_geometry_value(entity, 'unit_vector')
        
        if start and unit_vector:
            start_point = self._extract_point(start)
            # Создаем конечную точку для луча (в 10 раз дальше стартовой)
            end_point = (
                start_point[0] + 10 * self._extract_point(unit_vector)[0],
                start_point[1] + 10 * self._extract_point(unit_vector)[1],
                start_point[2] + 10 * self._extract_point(unit_vector)[2]
            )
            extra_data = self._build_extra_data(entity, {'start': start_point, 'unit_vector': unit_vector})
            return Result.success((LineString([start_point, end_point]), extra_data))
        
        extra_data = self._build_extra_data(entity)
        return Result.success((None, extra_data))

    def _convert_xline(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация XLINE (бесконечная линия)"""
        start = self._get_geometry_value(entity, 'start')
        unit_vector = self._get_geometry_value(entity, 'unit_vector')
        
        if start and unit_vector:
            start_point = self._extract_point(start)
            # Создаем бесконечную линию с большим диапазоном
            end_point = (
                start_point[0] + 1000 * self._extract_point(unit_vector)[0],
                start_point[1] + 1000 * self._extract_point(unit_vector)[1],
                start_point[2] + 1000 * self._extract_point(unit_vector)[2]
            )
            extra_data = self._build_extra_data(entity, {'start': start_point, 'unit_vector': unit_vector})
            return Result.success((LineString([start_point, end_point]), extra_data))
        
        extra_data = self._build_extra_data(entity)
        return Result.success((None, extra_data))

    # ========== Polyline Converters ==========

    def _convert_polyline(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация POLYLINE"""
        points_data = self._get_geometry_value(entity, 'points')
        if not points_data:
            return Result.fail("POLYLINE: missing points")
        
        points = [self._extract_point(p) for p in points_data]
        is_closed = self._get_geometry_value(entity, 'is_closed', False)
        
        extra_data = self._build_extra_data(entity, {'points': points, 'is_closed': is_closed})
        
        if is_closed and len(points) >= 3:
            return Result.success((Polygon(points), extra_data))
        else:
            return Result.success((LineString(points), extra_data))

    def _convert_lwpolyline(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация LWPOLYLINE (Light Weight Polyline)"""
        points_data = self._get_geometry_value(entity, 'points')
        if not points_data:
            return Result.fail("LWPOLYLINE: missing points")
        
        points = [self._extract_point(p) for p in points_data]
        is_closed = self._get_geometry_value(entity, 'is_closed', False)
        elevation = self._get_geometry_value(entity, 'elevation', 0)
        
        extra_data = self._build_extra_data(entity, {
            'points': points,
            'is_closed': is_closed,
            'elevation': elevation
        })
        
        if is_closed and len(points) >= 3:
            return Result.success((Polygon(points), extra_data))
        else:
            return Result.success((LineString(points), extra_data))

    # ========== Circle & Arc Converters ==========

    def _convert_circle(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация CIRCLE"""
        center = self._get_geometry_value(entity, 'center')
        radius = self._get_geometry_value(entity, 'radius')
        
        if not center or radius is None:
            return Result.fail("CIRCLE: missing center or radius")
        
        center_point = self._extract_point(center)
        
        # Создаем 100 точек для круга (достаточно для гладкого представления)
        angles = np.linspace(0, 2 * np.pi, 100)
        circle_points = [
            (center_point[0] + radius * np.cos(angle), 
             center_point[1] + radius * np.sin(angle), 
             center_point[2])
            for angle in angles
        ]
        
        extra_data = self._build_extra_data(entity, {'radius': radius})
        
        return Result.success((Polygon(circle_points), extra_data))

    def _convert_arc(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация ARC"""
        center = self._get_geometry_value(entity, 'center')
        radius = self._get_geometry_value(entity, 'radius')
        start_angle = self._get_geometry_value(entity, 'start_angle')
        end_angle = self._get_geometry_value(entity, 'end_angle')
        
        if not center or radius is None or start_angle is None or end_angle is None:
            return Result.fail("ARC: missing required parameters")
        
        center_point = self._extract_point(center)
        
        # Создаем точки для дуги (100 точек для гладкости)
        angles = np.linspace(np.radians(start_angle), np.radians(end_angle), 100)
        arc_points = [
            (center_point[0] + radius * np.cos(angle),
             center_point[1] + radius * np.sin(angle),
             center_point[2])
            for angle in angles
        ]
        
        extra_data = self._build_extra_data(entity, {
            'radius': radius,
            'start_angle': start_angle,
            'end_angle': end_angle
        })
        
        return Result.success((LineString(arc_points), extra_data))

    # ========== Ellipse Converter ==========

    def _convert_ellipse(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация ELLIPSE"""
        center = self._get_geometry_value(entity, 'center')
        major_axis = self._get_geometry_value(entity, 'major_axis')
        ratio = self._get_geometry_value(entity, 'ratio', 1.0)
        start_param = self._get_geometry_value(entity, 'start_param', 0)
        end_param = self._get_geometry_value(entity, 'end_param', 2 * np.pi)
        
        if not center or not major_axis:
            return Result.fail("ELLIPSE: missing center or major_axis")
        
        center_point = self._extract_point(center)
        major_axis_vec = self._extract_point(major_axis)
        
        # Создаем точки для эллипса
        angles = np.linspace(start_param, end_param, 100)
        ellipse_points = [
            (center_point[0] + major_axis_vec[0] * np.cos(angle) * ratio,
             center_point[1] + major_axis_vec[1] * np.sin(angle),
             center_point[2])
            for angle in angles
        ]
        
        extra_data = self._build_extra_data(entity, {
            'ratio': ratio,
            'start_param': start_param,
            'end_param': end_param
        })
        
        return Result.success((LineString(ellipse_points), extra_data))

    # ========== Text Converters ==========

    def _convert_text(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация TEXT"""
        insert = self._get_geometry_value(entity, 'insert')
        text = self._get_geometry_value(entity, 'text', '')
        height = self._get_geometry_value(entity, 'height', 0)
        rotation = self._get_geometry_value(entity, 'rotation', 0)
        
        if not insert:
            return Result.fail("TEXT: missing insert point")
        
        insert_point = self._extract_point(insert)
        extra_data = self._build_extra_data(entity, {
            'text': text,
            'height': height,
            'rotation': rotation
        })
        
        return Result.success((Point(*insert_point), extra_data))

    def _convert_mtext(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация MTEXT (многострочный текст)"""
        insert = self._get_geometry_value(entity, 'insert')
        text = self._get_geometry_value(entity, 'text', '')
        height = self._get_geometry_value(entity, 'height', 0)
        rotation = self._get_geometry_value(entity, 'rotation', 0)
        
        if insert:
            insert_point = self._extract_point(insert)
            geom = Point(*insert_point)
        else:
            geom = None
        
        extra_data = self._build_extra_data(entity, {
            'text': text,
            'height': height,
            'rotation': rotation
        })
        
        return Result.success((geom, extra_data))

    def _convert_attrib(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация ATTRIB (атрибут блока)"""
        insert = self._get_geometry_value(entity, 'insert')
        tag = self._get_geometry_value(entity, 'tag', '')
        text = self._get_geometry_value(entity, 'text', '')
        
        if insert:
            insert_point = self._extract_point(insert)
            geom = Point(*insert_point)
        else:
            geom = None
        
        extra_data = self._build_extra_data(entity, {
            'tag': tag,
            'text': text
        })
        
        return Result.success((geom, extra_data))

    # TODO: ATTDEF converter (определение атрибута) - обычно не имеет геометрии, но может содержать важные данные для атрибутов блоков
    
    # ========== Spline Converter ==========

    def _convert_spline(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация SPLINE (кривая Безье/Б-сплайн)"""
        points_data = self._get_geometry_value(entity, 'points')
        
        if not points_data or len(points_data) < 2:
            return Result.fail("SPLINE: missing or insufficient points")
        
        points = [self._extract_point(p) for p in points_data]
        extra_data = self._build_extra_data(entity, {'points': points})
        
        return Result.success((LineString(points), extra_data))

    # ========== 3D Face Converters ==========

    def _convert_3dface(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация 3DFACE"""
        vtx0 = self._get_geometry_value(entity, 'vtx0')
        vtx1 = self._get_geometry_value(entity, 'vtx1')
        vtx2 = self._get_geometry_value(entity, 'vtx2')
        vtx3 = self._get_geometry_value(entity, 'vtx3')
        
        if not all([vtx0, vtx1, vtx2, vtx3]):
            return Result.fail("3DFACE: missing vertices")
        
        points = [
            self._extract_point(vtx0),
            self._extract_point(vtx1),
            self._extract_point(vtx2),
            self._extract_point(vtx3)
        ]
        
        # Если четвертая вершина совпадает с первой, это треугольник
        if points[0] == points[3]:
            points.pop()
        
        extra_data = self._build_extra_data(entity, {'vertices': points})
        
        if len(points) >= 3:
            return Result.success((Polygon(points), extra_data))
        else:
            return Result.success((None, extra_data))

    def _convert_solid(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация SOLID (четырехугольник)"""
        return self._convert_3dface(entity)

    def _convert_trace(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация TRACE (аналогична SOLID)"""
        return self._convert_3dface(entity)

    # ========== 3D Object Converters ==========

    def _convert_3dsolid(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация 3DSOLID (3D объект)"""
        acis_data = self._get_geometry_value(entity, 'acis_data')
        extra_data = self._build_extra_data(entity, {'acis_data': acis_data})
        
        return Result.success((None, extra_data))

    def _convert_body(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация BODY (3D тело)"""
        acis_data = self._get_geometry_value(entity, 'acis_data')
        extra_data = self._build_extra_data(entity, {'acis_data': acis_data})
        return Result.success((None, extra_data))

    def _convert_region(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация REGION (3D регион)"""
        acis_data = self._get_geometry_value(entity, 'acis_data')
        extra_data = self._build_extra_data(entity, {'acis_data': acis_data})
        return Result.success((None, extra_data))

    # ========== Mesh Converters ==========

    def _convert_mesh(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация MESH (сетка)"""
        vertices = self._get_geometry_value(entity, 'vertices', [])
        faces = self._get_geometry_value(entity, 'faces', [])
        
        extra_data = self._build_extra_data(entity, {
            'vertices': vertices,
            'faces': faces
        })
        
        return Result.success((None, extra_data))

    def _convert_polymesh(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация POLYMESH"""
        extra_data = self._build_extra_data(entity)
        return Result.success((None, extra_data))

    def _convert_polyface(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация POLYFACE"""
        extra_data = self._build_extra_data(entity)
        return Result.success((None, extra_data))

    # ========== Hatch Converter ==========

    def _convert_hatch(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация HATCH (заливка)"""
        boundaries = self._get_geometry_value(entity, 'boundaries', [])
        pattern_name = self._get_geometry_value(entity, 'pattern_name', '')
        solid_fill = self._get_geometry_value(entity, 'solid_fill', False)
        
        if not boundaries:
            extra_data = self._build_extra_data(entity, {
                'pattern_name': pattern_name,
                'solid_fill': solid_fill
            })
            return Result.success((None, extra_data))
        
        polygons = []
        for boundary in boundaries:
            if isinstance(boundary, list) and len(boundary) >= 3:
                points = [self._extract_point(p) for p in boundary]
                if len(points) >= 3:
                    polygons.append(Polygon(points))
        
        extra_data = self._build_extra_data(entity, {
            'pattern_name': pattern_name,
            'solid_fill': solid_fill,
            'boundary_count': len(boundaries)
        })
        
        if len(polygons) == 0:
            return Result.success((None, extra_data))
        elif len(polygons) == 1:
            return Result.success((polygons[0], extra_data))
        else:
            return Result.success((MultiPolygon(polygons), extra_data))

    # ========== Leader Converter ==========

    def _convert_leader(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация LEADER"""
        vertices = self._get_geometry_value(entity, 'vertices', [])
        text = self._get_geometry_value(entity, 'text', '')
        
        if not vertices or len(vertices) < 2:
            extra_data = self._build_extra_data(entity, {'text': text})
            return Result.success((None, extra_data))
        
        points = [self._extract_point(v) for v in vertices]
        extra_data = self._build_extra_data(entity, {'text': text})
        
        return Result.success((LineString(points), extra_data))

    # ========== MultiLeader Converter ==========

    def _convert_multileader(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация MULTILEADER"""
        base_point = self._get_geometry_value(entity, 'base_point')
        text = self._get_geometry_value(entity, 'text', '')
        leader_lines = self._get_geometry_value(entity, 'leader_lines', [])
        char_height = self._get_geometry_value(entity, 'char_height')
        rotation = self._get_geometry_value(entity, 'rotation')
        
        if base_point:
            point = self._extract_point(base_point)
            geom = Point(*point)
        else:
            geom = Point(0, 0, 0)
        
        extra_data = self._build_extra_data(entity, {
            'text': text,
            'leader_lines': leader_lines,
            'char_height': char_height,
            'rotation': rotation
        })
        
        return Result.success((geom, extra_data))

    # ========== Block Insert Converter ==========

    def _convert_insert(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация INSERT (вставка блока)"""
        insert = self._get_geometry_value(entity, 'insert')
        name = self._get_geometry_value(entity, 'name', '')
        xscale = self._get_geometry_value(entity, 'xscale', 1.0)
        yscale = self._get_geometry_value(entity, 'yscale', 1.0)
        zscale = self._get_geometry_value(entity, 'zscale', 1.0)
        rotation = self._get_geometry_value(entity, 'rotation', 0)
        
        if not insert:
            extra_data = self._build_extra_data(entity, {'block_name': name})
            return Result.success((None, extra_data))
        
        insert_point = self._extract_point(insert)
        extra_data = self._build_extra_data(entity, {
            'block_name': name,
            'xscale': xscale,
            'yscale': yscale,
            'zscale': zscale,
            'rotation': rotation
        })
        
        return Result.success((Point(*insert_point), extra_data))

    def _convert_shape(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация SHAPE"""
        insert = self._get_geometry_value(entity, 'insert')
        name = self._get_geometry_value(entity, 'name', '')
        
        if insert:
            point = self._extract_point(insert)
            geom = Point(*point)
        else:
            geom = None
        
        extra_data = self._build_extra_data(entity, {'shape_name': name})
        return Result.success((geom, extra_data))

    # ========== Viewport & Image Converters ==========

    def _convert_viewport(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация VIEWPORT"""
        center = self._get_geometry_value(entity, 'center')
        width = self._get_geometry_value(entity, 'width')
        height = self._get_geometry_value(entity, 'height')
        
        if center:
            point = self._extract_point(center)
            geom = Point(*point)
        else:
            geom = None
        
        extra_data = self._build_extra_data(entity, {
            'width': width,
            'height': height
        })
        return Result.success((geom, extra_data))

    def _convert_image(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация IMAGE"""
        insert = self._get_geometry_value(entity, 'insert')
        u_pixel = self._get_geometry_value(entity, 'u_pixel')
        v_pixel = self._get_geometry_value(entity, 'v_pixel')
        
        if insert:
            point = self._extract_point(insert)
            geom = Point(*point)
        else:
            geom = None
        
        extra_data = self._build_extra_data(entity, {
            'u_pixel': u_pixel,
            'v_pixel': v_pixel
        })
        return Result.success((geom, extra_data))

    def _convert_imagedef(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация IMAGEDEF"""
        filename = self._get_geometry_value(entity, 'filename', '')
        extra_data = self._build_extra_data(entity, {'filename': filename})
        return Result.success((None, extra_data))

    # ========== Helix Converter ==========

    def _convert_helix(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация HELIX (спираль)"""
        base_point = self._get_geometry_value(entity, 'base_point')
        axis_vector = self._get_geometry_value(entity, 'axis_vector')
        radius = self._get_geometry_value(entity, 'radius', 1.0)
        turns = self._get_geometry_value(entity, 'turns', 1)
        height = self._get_geometry_value(entity, 'height', 1.0)
        
        if not base_point:
            extra_data = self._build_extra_data(entity)
            return Result.success((None, extra_data))
        
        base = self._extract_point(base_point)
        
        # Создаем точки для аппроксимации спирали
        angles = np.linspace(0, 2 * np.pi * turns, 100)
        helix_points = [
            (base[0] + radius * np.cos(angle),
             base[1] + radius * np.sin(angle),
             base[2] + (angle / (2 * np.pi * turns)) * height)
            for angle in angles
        ]
        
        extra_data = self._build_extra_data(entity, {
            'radius': radius,
            'turns': turns,
            'height': height
        })
        
        return Result.success((LineString(helix_points), extra_data))

    def _convert_vertex(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация VERTEX"""
        location = self._get_geometry_value(entity, 'insert')  # может быть как insert так и location
        if not location:
            location = self._get_geometry_value(entity, 'location')
        
        if location:
            point = self._extract_point(location)
            geom = Point(*point)
        else:
            geom = None
        
        extra_data = self._build_extra_data(entity)
        return Result.success((geom, extra_data))

    # ========== Dimension Converter ==========

    def _convert_dimension(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        """Конвертация DIMENSION"""
        extra_data = self._build_extra_data(entity)
        return Result.success((None, extra_data))

    # ========== Stub Converters (no geometry support) ==========

    def _convert_acad_proxy_entity(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        extra_data = self._build_extra_data(entity)
        return Result.success((None, extra_data))

    def _convert_mline(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        extra_data = self._build_extra_data(entity)
        return Result.success((None, extra_data))

    def _convert_mpolygon(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        extra_data = self._build_extra_data(entity)
        return Result.success((None, extra_data))

    def _convert_surface(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        extra_data = self._build_extra_data(entity)
        return Result.success((None, extra_data))

    def _convert_underlay(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        extra_data = self._build_extra_data(entity)
        return Result.success((None, extra_data))

    def _convert_wipeout(self, entity: DXFEntity) -> Result[Tuple[Optional[BaseGeometry], Dict[str, Any]]]:
        extra_data = self._build_extra_data(entity)
        return Result.success((None, extra_data))
