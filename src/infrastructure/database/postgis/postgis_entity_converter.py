
import json
from typing import Any, Dict, Optional, Tuple
from shapely.geometry.base import BaseGeometry
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
from ....domain.value_objects import Result
from ....domain.entities import DXFEntity

class PostGISEntityConverter:
    
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
        'XLINE': '_convert_xline'
    }

    def to_db(self, entity: DXFEntity) -> Result[Tuple[Any, Dict[str, Any]]]:
        convert_func_name = self._CONVERSION_FUNCTIONS.get(entity.entity_type.value)
        if convert_func_name:
            convert_func = getattr(self, convert_func_name)
            return convert_func(entity)
        return Result.fail(f"Unsupported entity type: {entity.entity_type}")
    
    def from_db(self, data: Dict[str, Any]) -> Result[DXFEntity]:
        pass
    
    def _convert_3dface(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
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
        extra_data = self._attributes_to_dict(entity)
        extra_data['points'] = points
        return Polygon(points), extra_data

    def _convert_3dsolid(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_acad_proxy_entity(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_arc(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_attrib(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_body(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_circle(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_dimension(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_arc_dimension(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass 

    def _convert_ellipse(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_hatch(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_helix(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_image(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_insert(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_leader(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_line(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_lwpolyline(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_mline(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass
    
    def _convert_mesh(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_mpolygon(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_mtext(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_multileader(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_point(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_polyline(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_vertex(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_polymesh(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_polyface(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_ray(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_region(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_shape(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_solid(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_spline(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_surface(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_text(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_trace(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_underlay(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_viewport(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_wipeout(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass

    def _convert_xline(self, entity: DXFEntity) -> Result[Tuple[BaseGeometry, Dict[str, Any]]]:
        pass


"""
def _convert_point_to_postgis(self, entity: DXFPoint) -> Tuple[BaseGeometry, Dict]:
        extra_data = self._attributes_to_dict(entity)
        return Point(entity.dxf.location.x, entity.dxf.location.y, entity.dxf.location.z), extra_data

    def _convert_line_to_postgis(self, entity: Line) -> Tuple[BaseGeometry, Dict]:
        extra_data = self._attributes_to_dict(entity)

        start = (entity.dxf.start.x, entity.dxf.start.y, entity.dxf.start.z)
        end = (entity.dxf.end.x, entity.dxf.end.y, entity.dxf.end.z)
        return LineString([start, end]), extra_data

    def _convert_polyline_to_postgis(self, entity: Polyline) -> Tuple[BaseGeometry, dict]:
        points = [(v.x, v.y, v.z) for v in entity.points()]
        
        extra_data = self._attributes_to_dict(entity)
        extra_data['points'] = points
        extra_data['attributes']['is_closed'] = entity.is_closed
        
        if entity.is_closed:
            return Polygon(points), extra_data
        else:
            return LineString(points), extra_data
        
    def _convert_lwpolyline_to_postgis(self, entity: LWPolyline) -> Tuple[BaseGeometry, dict]:
        points = [(v.x, v.y, v.z) for v in entity.vertices_in_ocs()]
        
        extra_data = self._attributes_to_dict(entity)
        extra_data['points'] = list(entity.get_points(format='xy'))
        extra_data['attributes']['is_closed'] = entity.is_closed
        
        if entity.is_closed:
            return Polygon(points), extra_data
        else:
            return LineString(points), extra_data
        
    def _convert_text_to_postgis(self, entity: Text) -> Tuple[BaseGeometry, dict]:
        extra_data = self._attributes_to_dict(entity)

        return Point(entity.dxf.insert.x, entity.dxf.insert.y, entity.dxf.insert.z), extra_data

    def _convert_circle_to_postgis(self, entity: Circle) -> Tuple[BaseGeometry, dict]:
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

        extra_data = self._attributes_to_dict(entity)
        return circle, extra_data

    def _convert_arc_to_postgis(self, entity: Arc) -> Tuple[BaseGeometry, dict]:
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

        extra_data = self._attributes_to_dict(entity)
        return arc, extra_data

    def _convert_multileader_to_postgis(self, entity: MultiLeader) -> Tuple[Union[Polygon, Point], dict]:
        extra_data = self._attributes_to_dict(entity)
        #Logger.log_message(f'MULTILEADER: {extra_data}')
        # Note: dxf_handler not passed, assuming it's available or not needed
        # text_style_entity = dxf_handler.get_entity_db(extra_data['attributes']['text_style_handle'])

        # extra_data['text_style'] = text_style_entity.dxf.name
        extra_data['char_height'] = entity.context.char_height
        extra_data['rotation'] = entity.context.mtext.rotation

       # Извлекаем текстовое содержимое, если есть
        if entity.has_mtext_content:
            extra_data['text'] = entity.get_mtext_content()
        elif entity.has_block_content:
            extra_data['block_attributes'] = entity.get_block_content()

        if entity.has_block_content:
            Logger.log_message(entity.get_block_content())
        # Извлекаем линии-указатели
        leader_lines = []
        for leader in entity.context.leaders:
            for line in leader.lines:
                leader_lines.append(line.vertices)
                #Logger.log_message(f'Линия лидера с вершинами: {leader_lines}')
        extra_data['leader_lines'] = leader_lines

        # Попытка получить координаты из dxf.insert, если есть
        base_point = entity.context.base_point
        if base_point is None:
            base_point = (0, 0, 0)
        else:
            base_point = (base_point.x, base_point.y, base_point.z)
            #Logger.log_message(f'MULTILEADER base_point: {base_point}')

        extra_data['base_point'] = base_point
        
        geometry = Point(*base_point) if base_point else None
        return geometry, extra_data

    def _convert_insert_to_postgis(self, entity: Insert) -> Tuple[BaseGeometry, dict]:
        insertion_point = (entity.dxf.insert.x, entity.dxf.insert.y, entity.dxf.insert.z)

        # Получаем имя блока
        block_name = entity.dxf.name

        extra_data = self._attributes_to_dict(entity)
        extra_data['block_name'] = block_name

        # Возвращаем точку как представление вставки
        return Point(insertion_point), extra_data  # Используем точку как геометрию, можно изменить на нужный тип

    def _convert_3dsolid_to_postgis(self, entity: Solid3d) -> Tuple[Point, dict]:
        try:
            # Экспорт данных ACIS из объекта 3DSOLID
            acis_data = entity.acis_data  # Получаем двоичные данные ACIS
        except Exception as e:
            Logger.log_error("_convert_3dsolid_to_postgis() ERROR. e: " + str(e))
            return None, {}
        
        # Собираем дополнительные данные, такие как объем, если он доступен
        extra_data = self._attributes_to_dict(entity)
        extra_data['acis_data'] = acis_data

        return None, extra_data

    def _convert_spline_to_postgis(self, entity: Spline) -> Tuple[BaseGeometry, dict]:
        SPLINE в DXF представляет собой кривую Безье или Б-сплайн. В Shapely нет прямого эквивалента, но можно аппроксимировать кривую точками.
        points = [tuple(v) for v in entity.flattening(0.01)]
        extra_data = self._attributes_to_dict(entity)
        extra_data['points'] = points
        return LineString(points), extra_data

    def _convert_ellipse_to_postgis(self, entity: Ellipse) -> Tuple[BaseGeometry, dict]:
        ELLIPSE в DXF представляет собой эллипс. В Shapely можно аппроксимировать эллипс точками.
        center = (entity.dxf.center.x, entity.dxf.center.y, entity.dxf.center.z)
        major_axis = (entity.dxf.major_axis.x, entity.dxf.major_axis.y, entity.dxf.major_axis.z)
        ratio = entity.dxf.ratio
        extrusion = entity.dxf.extrusion
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

        extra_data = self._attributes_to_dict(entity)
        return LineString(ellipse_points), extra_data

    def _convert_mtext_to_postgis(self, entity: MText) -> Tuple[BaseGeometry, dict]:
        MTEXT в DXF представляет собой многострочный текст. В Shapely нет прямого эквивалента, но можно сохранить текст и его позицию.
        extra_data = self._attributes_to_dict(entity)
        extra_data['text'] = entity.text
        Logger.log_message(extra_data)
        return None, extra_data

    def _convert_solid_to_postgis(self, entity: Solid) -> Tuple[BaseGeometry, dict]:
        SOLID` в DXF представляет собой четырехугольник. В Shapely можно представить его как `Polygon`
        points = [
            (entity.dxf.vtx0.x, entity.dxf.vtx0.y, entity.dxf.vtx0.z),
            (entity.dxf.vtx1.x, entity.dxf.vtx1.y, entity.dxf.vtx1.z),
            (entity.dxf.vtx2.x, entity.dxf.vtx2.y, entity.dxf.vtx2.z),
            (entity.dxf.vtx3.x, entity.dxf.vtx3.y, entity.dxf.vtx3.z)
        ]
        extra_data = self._attributes_to_dict(entity)
        extra_data['points'] = points
        return Polygon(points), extra_data

    def _convert_trace_to_postgis(self, entity: Trace) -> Tuple[BaseGeometry, dict]:
        `TRACE` в DXF также представляет собой четырехугольник. Обработка аналогична `SOLID`.
        points = [
            (entity.dxf.vtx0.x, entity.dxf.vtx0.y, entity.dxf.vtx0.z),
            (entity.dxf.vtx1.x, entity.dxf.vtx1.y, entity.dxf.vtx1.z),
            (entity.dxf.vtx2.x, entity.dxf.vtx2.y, entity.dxf.vtx2.z),
            (entity.dxf.vtx3.x, entity.dxf.vtx3.y, entity.dxf.vtx3.z)
        ]
        extra_data = self._attributes_to_dict(entity)
        extra_data['points'] = points
        return Polygon(points), extra_data

    def _convert_3dface_to_postgis(self, entity: Face3d) -> Tuple[BaseGeometry, dict]:
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
        extra_data = self._attributes_to_dict(entity)
        extra_data['points'] = points
        return Polygon(points), extra_data

    def _convert_region_to_postgis(self, entity: Region) -> Tuple[BaseGeometry, dict]:
        '''`REGION` в DXF представляет собой трехмерный регион. В Shapely нет прямого эквивалента, но можно сохранить ACIS данные.'''
        try:
            acis_data = entity.acis_data
        except Exception as e:
            Logger.log_error("_convert_region_to_postgis() ERROR. e: " + str(e))
            return None, {}

        extra_data = self._attributes_to_dict(entity)
        extra_data['acis_data'] = acis_data

        return None, extra_data

    def _convert_body_to_postgis(self, entity: Body) -> Tuple[BaseGeometry, dict]:
        '''`BODY` в DXF представляет собой трехмерное тело. В Shapely нет прямого эквивалента, но можно сохранить ACIS данные.'''
        try:
            acis_data = entity.acis_data
        except Exception as e:
            Logger.log_error("_convert_body_to_postgis() ERROR. e: " + str(e))
            return None, {}

        extra_data = self._attributes_to_dict(entity)
        extra_data['acis_data'] = acis_data

        return None, extra_data

    def _convert_mesh_to_postgis(self, entity: Mesh) -> Tuple[BaseGeometry, dict]:
        '''`MESH` в DXF представляет собой сетку. В Shapely нет прямого эквивалента, но можно сохранить вершины и грани.'''
        vertices = [tuple(v) for v in entity.vertices()]
        faces = [tuple(f) for f in entity.faces()]
        extra_data = self._attributes_to_dict(entity)
        extra_data['vertices'] = vertices
        extra_data['faces'] = faces
        return None, extra_data

    def _convert_hatch_to_postgis(self, entity: Hatch) -> Tuple[BaseGeometry, dict]:
        '''`HATCH` в DXF представляет собой заливку. В Shapely можно представить его как `Polygon`.'''
        Logger.log_message(f'HATCH: {entity.dxf.pattern_name}')
        polygons = []
        for boundary in entity.paths:
            points = [tuple(v) for v in boundary.vertices()]
            polygons.append(Polygon(points))
        extra_data = self._attributes_to_dict(entity)
        if len(polygons) == 1:
            return polygons[0], extra_data
        else:
            return MultiPolygon(polygons), extra_data

    def _convert_leader_to_postgis(self, entity: Leader) -> Tuple[BaseGeometry, dict]:
        '''`LEADER` в DXF представляет собой линию с текстом. В Shapely можно представить его как `LineString` и сохранить текст.'''
        points = [tuple(v) for v in entity.vertices()]
        extra_data = self._attributes_to_dict(entity)
        extra_data['text'] = entity.dxf.text
        return LineString(points), extra_data

    def _convert_shape_to_postgis(self, entity: Shape) -> Tuple[BaseGeometry, dict]:
        '''`SHAPE` в DXF представляет собой встроенный двумерный объект. В Shapely нет прямого эквивалента, но можно сохранить данные о блоке.'''
        insertion_point = (entity.dxf.insert.x, entity.dxf.insert.y, entity.dxf.insert.z)
        block_name = entity.dxf.name
        extra_data = self._attributes_to_dict(entity)
        extra_data['block_name'] = block_name
        return Point(insertion_point), extra_data

    def _convert_viewport_to_postgis(self, entity: Viewport) -> Tuple[BaseGeometry, dict]:
        '''`VIEWPORT` в DXF представляет собой область просмотра. В Shapely нет прямого эквивалента, но можно сохранить данные о области.'''
        center = (entity.dxf.center.x, entity.dxf.center.y, entity.dxf.center.z)
        width = entity.dxf.width
        height = entity.dxf.height
        extra_data = self._attributes_to_dict(entity)
        extra_data['width'] = width
        extra_data['height'] = height
        return Point(center), extra_data

    def _convert_image_to_postgis(self, entity: Image) -> Tuple[BaseGeometry, dict]:
        '''`IMAGE` в DXF представляет собой изображение. В Shapely нет прямого эквивалента, но можно сохранить данные о изображении.'''
        insertion_point = (entity.dxf.insert.x, entity.dxf.insert.y, entity.dxf.insert.z)
        u_size = entity.dxf.u_size
        v_size = entity.dxf.v_size
        image_def_handle = entity.dxf.image_def_handle
        extra_data = self._attributes_to_dict(entity)
        extra_data['insertion_point'] = insertion_point
        extra_data['u_size'] = u_size
        extra_data['v_size'] = v_size
        extra_data['image_def_handle'] = image_def_handle
        return Point(insertion_point), extra_data

    def _convert_imagedef_to_postgis(self, entity: ImageDef) -> Tuple[BaseGeometry, dict]:
        '''`IMAGEDEF` в DXF представляет собой определение изображения. В Shapely нет прямого эквивалента, но можно сохранить данные о изображении.'''
        filename = entity.dxf.filename
        extra_data = self._attributes_to_dict(entity)
        extra_data['filename'] = filename
        return None, extra_data

    def _convert_dimension_to_postgis(self, entity: Dimension) -> Tuple[BaseGeometry, dict]:
        '''`DIMENSION` в DXF представляет собой измерение. В Shapely нет прямого эквивалента, но можно сохранить данные об измерении.'''
        extra_data = self._attributes_to_dict(entity)
        return None, extra_data

    def _convert_ray_to_postgis(self, entity: Ray) -> Tuple[BaseGeometry, dict]:
        '''`RAY` в DXF представляет собой луч. В Shapely нет прямого эквивалента, но можно сохранить данные о луче.'''
        start_point = (entity.dxf.start.x, entity.dxf.start.y, entity.dxf.start.z)
        unit_vector = (entity.dxf.unit_vector.x, entity.dxf.unit_vector.y, entity.dxf.unit_vector.z)
        extra_data = self._attributes_to_dict(entity)
        extra_data['start_point'] = start_point
        extra_data['unit_vector'] = unit_vector
        return Point(start_point), extra_data

    def _convert_xline_to_postgis(self, entity: XLine) -> Tuple[BaseGeometry, dict]:
        '''`XLINE` в DXF представляет собой бесконечную линию. В Shapely нет прямого эквивалента, но можно сохранить данные о линии.'''
        start_point = (entity.dxf.start.x, entity.dxf.start.y, entity.dxf.start.z)
        unit_vector = (entity.dxf.unit_vector.x, entity.dxf.unit_vector.y, entity.dxf.unit_vector.z)
        extra_data = self._attributes_to_dict(entity)
        extra_data['start_point'] = start_point
        extra_data['unit_vector'] = unit_vector
        return Point(start_point), extra_data

    def _convert_attrib_to_postgis(self, entity: Attrib):
        '''`ATTRIB` в DXF представляет собой атрибут блока. В Shapely нет прямого эквивалента, но можно сохранить данные об атрибуте.'''
        return Point(entity.dxf.insert.x, entity.dxf.insert.y, entity.dxf.insert.z), self._attributes_to_dict(entity)

    def _convert_vertex_to_postgis(self, entity: Vertex) -> Tuple[BaseGeometry, dict]:
        '''`VERTEX` в DXF представляет собой вершину. В Shapely нет прямого эквивалента, но можно сохранить данные о вершине.'''
        location = (entity.point.location.x, entity.point.location.y, entity.point.location.z)
        extra_data = self._attributes_to_dict(entity)
        extra_data['location'] = location
        return Point(location), extra_data

    def _convert_seqend_to_postgis(self, entity: SeqEnd) -> Tuple[BaseGeometry, dict]:
        '''`SEQEND` в DXF представляет собой конец последовательности. В Shapely нет прямого эквивалента, но можно сохранить данные о последовательности.'''
        extra_data = self._attributes_to_dict(entity)
        return None, extra_data

    def _convert_helix_to_postgis(self, entity: Helix) -> Tuple[BaseGeometry, dict]:
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

        extra_data = self._attributes_to_dict(entity)
        return LineString(helix_points), extra_data
"""