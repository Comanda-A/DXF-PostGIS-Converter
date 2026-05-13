
import os
import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext, layout, svg
from ezdxf.entities import DXFEntity as EzDXFEntity
from ezdxf.math import Vec3
from ...domain.value_objects import Result, DxfEntityType
from ...domain.entities import DXFDocument, DXFContent, DXFLayer, DXFEntity
from ...domain.services import IDXFReader

class DXFReader(IDXFReader):
    """
    Считывает DXF файлы и организует данные для конвертации в PostGIS.
    
    Выполняет полную экстракцию всех необходимых геометрических и атрибутивных
    данных из DXF сущностей для корректной конвертации в PostGIS формат.
    """

    def open(self, filepath: str) -> Result[DXFDocument]:
        try:
            # Открываем DXF файл с помощью ezdxf и выполняем базовую проверку
            drawing = ezdxf.readfile(filepath)
            drawing.audit()
            msp = drawing.modelspace()
            # keep drawing reference for block extraction in geometry methods
            self._drawing = drawing
            # track visited blocks to avoid infinite recursion when blocks reference other blocks
            self._visited_blocks = set()

            filename = os.path.basename(filepath)

            doc = DXFDocument.create(
                filename=filename,
                filepath=filepath
            )

            # Читаем содержимое файла в байтах для хранения в базе данных
            with open(filepath, 'rb') as f:
                content = f.read()

            doc.add_content(
                DXFContent.create(
                    document_id=doc.id,
                    content=content
                )
            )

            layer_name: str
            dxfentities: list[EzDXFEntity]
            dxfentity: EzDXFEntity

            for layer_name, dxfentities in msp.groupby(dxfattrib="layer").items():
                # Создаем слой
                layer = DXFLayer.create(
                    document_id=doc.id,
                    name=layer_name,
                    schema_name="public",
                    table_name=layer_name
                )
                # Добавляем слой в документ
                doc.add_layers([layer])
                
                for dxfentity in dxfentities:
                    # Создаем сущность
                    entity = DXFEntity.create(
                        entity_type=DxfEntityType(dxfentity.dxftype()),
                        name=str(dxfentity)
                    )
                    
                    # Добавляем все базовые атрибуты
                    self._extract_base_attributes(dxfentity, entity)
                    
                    # Добавляем специфичные геометрические данные в зависимости от типа
                    self._extract_geometry_data(dxfentity, entity)
                    
                    # Добавляем сущность в слой
                    layer.add_entities([entity])
            # clear drawing reference and visited state
            self._drawing = None
            try:
                del self._visited_blocks
            except Exception:
                pass

            return Result.success(doc)
        except Exception as e:
            return Result.fail(f"Failed to open DXF file: {str(e)}")

    def _extract_base_attributes(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """Извлекает базовые атрибуты DXF сущности"""
        attributes = dxfentity.dxfattribs()
        
        # Добавляем базовые DXF атрибуты
        attributes['color'] = dxfentity.dxf.color
        attributes['linetype'] = dxfentity.dxf.linetype
        attributes['lineweight'] = dxfentity.dxf.lineweight
        attributes['ltscale'] = dxfentity.dxf.ltscale
        attributes['invisible'] = dxfentity.dxf.invisible
        attributes['true_color'] = dxfentity.dxf.true_color
        attributes['transparency'] = dxfentity.dxf.transparency
        
        entity.add_attributes(attributes)
        
        # Собираем данные для ezdxf.xref.write_block
        extra_data = {
            "dxftype": dxfentity.dxftype(),
            "dxf_attribs": {}
        }
        
        for key, value in attributes.items():
            if hasattr(value, "x"): # Векторы
                extra_data["dxf_attribs"][key] = [value.x, getattr(value, "y", 0.0), getattr(value, "z", 0.0)]
            elif isinstance(value, (int, float, str, bool, list, tuple)):
                extra_data["dxf_attribs"][key] = value
            else:
                extra_data["dxf_attribs"][key] = str(value)

        # Preserve source layer style so ByLayer entities keep visual appearance after TABLES reconstruction.
        try:
            layer_name = str(getattr(dxfentity.dxf, 'layer', '') or '')
            if layer_name and hasattr(self, '_drawing') and self._drawing is not None and layer_name in self._drawing.layers:
                layer = self._drawing.layers.get(layer_name)
                layer_attribs = {}
                for key in ('color', 'linetype', 'lineweight', 'plot', 'true_color', 'transparency', 'ltscale'):
                    try:
                        value = getattr(layer.dxf, key)
                    except Exception:
                        continue

                    if value is None:
                        continue

                    if hasattr(value, 'x'):
                        layer_attribs[key] = [value.x, getattr(value, 'y', 0.0), getattr(value, 'z', 0.0)]
                    elif isinstance(value, (int, float, str, bool, list, tuple)):
                        layer_attribs[key] = value
                    else:
                        layer_attribs[key] = str(value)

                if layer_attribs:
                    extra_data['layer_name'] = layer_name
                    extra_data['layer_dxf_attribs'] = layer_attribs
        except Exception:
            pass
                
        entity.add_extra_data(extra_data)

    def _extract_geometry_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """Извлекает все геометрические данные в зависимости от типа сущности"""
        entity_type = dxfentity.dxftype()
        
        geometry_methods = {
            'POINT': self._extract_point_data,
            'LINE': self._extract_line_data,
            'POLYLINE': self._extract_polyline_data,
            'LWPOLYLINE': self._extract_lwpolyline_data,
            'CIRCLE': self._extract_circle_data,
            'ARC': self._extract_arc_data,
            'ELLIPSE': self._extract_ellipse_data,
            'SPLINE': self._extract_spline_data,
            'TEXT': self._extract_text_data,
            'MTEXT': self._extract_mtext_data,
            'INSERT': self._extract_insert_data,
            'MULTILEADER': self._extract_multileader_data,
            '3DFACE': self._extract_3dface_data,
            'SOLID': self._extract_solid_data,
            'TRACE': self._extract_trace_data,
            '3DSOLID': self._extract_3dsolid_data,
            'BODY': self._extract_body_data,
            'REGION': self._extract_region_data,
            'MESH': self._extract_mesh_data,
            'HATCH': self._extract_hatch_data,
            'LEADER': self._extract_leader_data,
            'RAY': self._extract_ray_data,
            'XLINE': self._extract_xline_data,
            'ATTRIB': self._extract_attrib_data,
            'SHAPE': self._extract_shape_data,
            'VIEWPORT': self._extract_viewport_data,
            'IMAGE': self._extract_image_data,
            'IMAGEDEF': self._extract_imagedef_data,
            'DIMENSION': self._extract_dimension_data,
            'HELIX': self._extract_helix_data,
        }
        
        if entity_type in geometry_methods:
            geometry_methods[entity_type](dxfentity, entity)

    def _vec3_to_list(self, vec3) -> list:
        """Конвертирует Vec3 в список координат"""
        if hasattr(vec3, 'x') and hasattr(vec3, 'y') and hasattr(vec3, 'z'):
            return [vec3.x, vec3.y, vec3.z]
        return vec3

    def _extract_point_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """POINT"""
        geometry = {
            'location': self._vec3_to_list(dxfentity.dxf.location)
        }
        entity.add_geometries(geometry)

    def _extract_line_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """LINE"""
        geometry = {
            'start': self._vec3_to_list(dxfentity.dxf.start),
            'end': self._vec3_to_list(dxfentity.dxf.end)
        }
        entity.add_geometries(geometry)

    def _extract_polyline_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """POLYLINE"""
        points = [self._vec3_to_list(v) for v in dxfentity.points()]
        geometry = {
            'points': points,
            'is_closed': dxfentity.is_closed
        }
        entity.add_geometries(geometry)
        entity.add_attributes({'is_closed': dxfentity.is_closed})

    def _extract_lwpolyline_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """LWPOLYLINE"""
        points = []
        try:
            for point in dxfentity.get_points("xyseb"):
                points.append(list(point))
        except Exception:
            points = [list(v) for v in dxfentity.vertices_in_ocs()]
        geometry = {
            'points': points,
            'is_closed': dxfentity.is_closed,
            'elevation': dxfentity.dxf.elevation,
            'const_width': dxfentity.dxf.const_width
        }
        entity.add_geometries(geometry)
        entity.add_attributes({'is_closed': dxfentity.is_closed})

    def _extract_circle_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """CIRCLE"""
        geometry = {
            'center': self._vec3_to_list(dxfentity.dxf.center),
            'radius': dxfentity.dxf.radius
        }
        entity.add_geometries(geometry)
        entity.add_attributes({'radius': dxfentity.dxf.radius})

    def _extract_arc_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """ARC"""
        geometry = {
            'center': self._vec3_to_list(dxfentity.dxf.center),
            'radius': dxfentity.dxf.radius,
            'start_angle': dxfentity.dxf.start_angle,
            'end_angle': dxfentity.dxf.end_angle
        }
        entity.add_geometries(geometry)
        entity.add_attributes({
            'radius': dxfentity.dxf.radius,
            'start_angle': dxfentity.dxf.start_angle,
            'end_angle': dxfentity.dxf.end_angle
        })

    def _extract_ellipse_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """ELLIPSE"""
        geometry = {
            'center': self._vec3_to_list(dxfentity.dxf.center),
            'major_axis': self._vec3_to_list(dxfentity.dxf.major_axis),
            'ratio': dxfentity.dxf.ratio,
            'start_param': dxfentity.dxf.start_param,
            'end_param': dxfentity.dxf.end_param,
            'extrusion': self._vec3_to_list(dxfentity.dxf.extrusion)
        }
        entity.add_geometries(geometry)
        entity.add_attributes({
            'ratio': dxfentity.dxf.ratio,
            'start_param': dxfentity.dxf.start_param,
            'end_param': dxfentity.dxf.end_param
        })

    def _extract_spline_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """SPLINE"""
        try:
            points = [list(v) for v in dxfentity.flattening(0.01)]
            geometry = {
                'points': points,
                'degree': dxfentity.dxf.degree
            }
            entity.add_geometries(geometry)
        except:
            pass

    def _extract_text_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """TEXT"""
        geometry = {
            'insert': self._vec3_to_list(dxfentity.dxf.insert),
            'text': dxfentity.dxf.text,
            'height': dxfentity.dxf.height,
            'rotation': dxfentity.dxf.rotation,
            'oblique': dxfentity.dxf.oblique,
            'style': dxfentity.dxf.style,
            'halign': dxfentity.dxf.halign,
            'valign': dxfentity.dxf.valign,
            'color': getattr(dxfentity.dxf, 'color', None),
            'true_color': getattr(dxfentity.dxf, 'true_color', None),
            'transparency': getattr(dxfentity.dxf, 'transparency', None),
        }
        entity.add_geometries(geometry)
        entity.add_attributes({
            'text': dxfentity.dxf.text,
            'height': dxfentity.dxf.height,
            'rotation': dxfentity.dxf.rotation
        })

    def _extract_mtext_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """MTEXT"""
        geometry = {
            'insert': self._vec3_to_list(dxfentity.dxf.insert),
            'text': dxfentity.text,
            'height': dxfentity.dxf.char_height,
            'rotation': dxfentity.dxf.rotation,
            'color': getattr(dxfentity.dxf, 'color', None),
            'true_color': getattr(dxfentity.dxf, 'true_color', None),
            'transparency': getattr(dxfentity.dxf, 'transparency', None),
        }
        entity.add_geometries(geometry)
        entity.add_attributes({
            'text': dxfentity.text,
            'height': dxfentity.dxf.char_height,
            'rotation': dxfentity.dxf.rotation
        })

    def _extract_insert_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """INSERT"""
        insert_attribs = []
        try:
            for attrib in getattr(dxfentity, 'attribs', []):
                insert_attribs.append({
                    'tag': getattr(attrib.dxf, 'tag', ''),
                    'text': getattr(attrib.dxf, 'text', ''),
                    'insert': self._vec3_to_list(getattr(attrib.dxf, 'insert', (0.0, 0.0, 0.0))),
                    'height': getattr(attrib.dxf, 'height', None),
                    'rotation': getattr(attrib.dxf, 'rotation', None),
                    'style': getattr(attrib.dxf, 'style', None),
                    'layer': getattr(attrib.dxf, 'layer', None),
                    'color': getattr(attrib.dxf, 'color', None),
                    'true_color': getattr(attrib.dxf, 'true_color', None),
                    'transparency': getattr(attrib.dxf, 'transparency', None),
                })
        except Exception:
            insert_attribs = []

        geometry = {
            'insert': self._vec3_to_list(dxfentity.dxf.insert),
            'name': dxfentity.dxf.name,
            'xscale': dxfentity.dxf.xscale,
            'yscale': dxfentity.dxf.yscale,
            'zscale': dxfentity.dxf.zscale,
            'rotation': dxfentity.dxf.rotation,
            'insert_attribs': insert_attribs,
        }
        entity.add_geometries(geometry)
        entity.add_attributes({
            'name': dxfentity.dxf.name,
            'xscale': dxfentity.dxf.xscale,
            'yscale': dxfentity.dxf.yscale,
            'zscale': dxfentity.dxf.zscale,
            'rotation': dxfentity.dxf.rotation
        })

        # If the referenced block exists in the drawing, serialize its entities recursively.
        try:
            block_name = dxfentity.dxf.name
            serialized = self._serialize_block_entities(block_name)
            # Keep block name even if serialized content is empty, so writer can create placeholder definition.
            entity.add_extra_data({'block_name': block_name, 'block_entities': serialized or []})
        except Exception:
            pass

    def _serialize_block_entities(self, block_name: str) -> list[dict]:
        if not (hasattr(self, '_drawing') and self._drawing is not None):
            return []

        if block_name not in self._drawing.blocks:
            return []

        visited = getattr(self, '_visited_blocks', set())
        if block_name in visited:
            return []

        visited.add(block_name)
        try:
            block_layout = self._drawing.blocks.get(block_name)
            serialized: list[dict] = []
            for block_entity in block_layout:
                payload = self._serialize_entity_for_block(block_entity)
                if payload:
                    serialized.append(payload)
            return serialized
        finally:
            try:
                visited.remove(block_name)
            except Exception:
                pass

    def _serialize_entity_for_block(self, dxfentity: EzDXFEntity) -> dict:
        try:
            payload_entity = DXFEntity.create(entity_type=DxfEntityType(dxfentity.dxftype()), name=str(dxfentity))
            self._extract_base_attributes(dxfentity, payload_entity)
            self._extract_geometry_data(dxfentity, payload_entity)

            payload: dict = {
                'dxftype': dxfentity.dxftype(),
                'dxf_attribs': dict(payload_entity.extra_data.get('dxf_attribs', {}) or {}),
                'attributes': dict(payload_entity.attributes or {}),
                'geometries': dict(payload_entity.geometries or {}),
            }

            if dxfentity.dxftype() == 'INSERT':
                nested_block_name = getattr(dxfentity.dxf, 'name', '')
                if nested_block_name:
                    nested = self._serialize_block_entities(nested_block_name)
                    payload['block_name'] = nested_block_name
                    payload['block_entities'] = nested or []

            return payload
        except Exception:
            return {}

    def _extract_multileader_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """MULTILEADER"""
        geometry = {}
        attributes = {}
        
        try:
            # Извлекаем текстовое содержимое
            if hasattr(dxfentity, 'get_mtext_content'):
                geometry['text'] = dxfentity.get_mtext_content()
            elif hasattr(dxfentity, 'text'):
                geometry['text'] = dxfentity.text
            
            # Базовая точка
            if hasattr(dxfentity, 'context') and hasattr(dxfentity.context, 'mtext'):
                try:
                    geometry['base_point'] = self._vec3_to_list(dxfentity.context.mtext.insert)
                except Exception:
                    pass
            if 'base_point' not in geometry and hasattr(dxfentity, 'dxf') and hasattr(dxfentity.dxf, 'insert'):
                geometry['base_point'] = self._vec3_to_list(dxfentity.dxf.insert)
            
            # Линии-указатели
            if hasattr(dxfentity, 'context') and hasattr(dxfentity.context, 'leaders'):
                leader_lines = []
                for leader in dxfentity.context.leaders:
                    if hasattr(leader, 'lines'):
                        for line in leader.lines:
                            if hasattr(line, 'vertices'):
                                leader_lines.append([self._vec3_to_list(v) for v in line.vertices])
                geometry['leader_lines'] = leader_lines
            
            # Другие параметры
            if hasattr(dxfentity, 'context'):
                if hasattr(dxfentity.context, 'char_height'):
                    geometry['char_height'] = dxfentity.context.char_height
                if hasattr(dxfentity.context, 'mtext') and hasattr(dxfentity.context.mtext, 'rotation'):
                    geometry['rotation'] = dxfentity.context.mtext.rotation
                if hasattr(dxfentity.context, 'leaders'):
                    leader_props = []
                    for leader in dxfentity.context.leaders:
                        leader_props.append({
                            'attachment_direction': getattr(leader, 'attachment_direction', None),
                            'dogleg_length': getattr(leader, 'dogleg_length', None),
                            'dogleg_vector': self._vec3_to_list(getattr(leader, 'dogleg_vector', None)) if getattr(leader, 'dogleg_vector', None) is not None else None,
                            'has_horizontal_attachment': getattr(leader, 'has_horizontal_attachment', None),
                            'has_dogleg_vector': getattr(leader, 'has_dogleg_vector', None),
                            'last_leader_point': self._vec3_to_list(getattr(leader, 'last_leader_point', None)) if getattr(leader, 'last_leader_point', None) is not None else None,
                        })
                    geometry['leader_properties'] = leader_props
        except:
            pass
        
        entity.add_geometries(geometry)
        entity.add_attributes(attributes)

    def _extract_3dface_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """3DFACE"""
        geometry = {
            'vtx0': self._vec3_to_list(dxfentity.dxf.vtx0),
            'vtx1': self._vec3_to_list(dxfentity.dxf.vtx1),
            'vtx2': self._vec3_to_list(dxfentity.dxf.vtx2),
            'vtx3': self._vec3_to_list(dxfentity.dxf.vtx3)
        }
        entity.add_geometries(geometry)

    def _extract_solid_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """SOLID"""
        geometry = {
            'vtx0': self._vec3_to_list(dxfentity.dxf.vtx0),
            'vtx1': self._vec3_to_list(dxfentity.dxf.vtx1),
            'vtx2': self._vec3_to_list(dxfentity.dxf.vtx2),
            'vtx3': self._vec3_to_list(dxfentity.dxf.vtx3)
        }
        entity.add_geometries(geometry)

    def _extract_trace_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """TRACE"""
        geometry = {
            'vtx0': self._vec3_to_list(dxfentity.dxf.vtx0),
            'vtx1': self._vec3_to_list(dxfentity.dxf.vtx1),
            'vtx2': self._vec3_to_list(dxfentity.dxf.vtx2),
            'vtx3': self._vec3_to_list(dxfentity.dxf.vtx3)
        }
        entity.add_geometries(geometry)

    def _extract_3dsolid_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """3DSOLID"""
        try:
            geometry = {
                'acis_data': dxfentity.acis_data if hasattr(dxfentity, 'acis_data') else None
            }
            entity.add_geometries(geometry)
        except:
            pass

    def _extract_body_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """BODY"""
        try:
            geometry = {
                'acis_data': dxfentity.acis_data if hasattr(dxfentity, 'acis_data') else None
            }
            entity.add_geometries(geometry)
        except:
            pass

    def _extract_region_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """REGION"""
        try:
            geometry = {
                'acis_data': dxfentity.acis_data if hasattr(dxfentity, 'acis_data') else None
            }
            entity.add_geometries(geometry)
        except:
            pass

    def _extract_mesh_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """MESH"""
        try:
            vertices = [self._vec3_to_list(v) for v in dxfentity.vertices()]
            faces = [list(f) for f in dxfentity.faces()]
            geometry = {
                'vertices': vertices,
                'faces': faces
            }
            entity.add_geometries(geometry)
        except:
            pass

    def _extract_hatch_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """HATCH"""
        try:
            boundaries = []
            hatch_paths = []
            if hasattr(dxfentity, 'paths'):
                for boundary in dxfentity.paths:
                    path_payload = {}
                    if hasattr(boundary, 'vertices'):
                        points = []
                        for vertex in boundary.vertices:
                            if isinstance(vertex, (list, tuple)):
                                if len(vertex) >= 3:
                                    points.append([float(vertex[0]), float(vertex[1]), float(vertex[2])])
                                elif len(vertex) >= 2:
                                    points.append([float(vertex[0]), float(vertex[1])])
                            else:
                                points.append(self._vec3_to_list(vertex))
                        boundaries.append(points)
                        path_payload = {
                            'path_type': 'polyline',
                            'is_closed': bool(getattr(boundary, 'is_closed', True)),
                            'vertices': points,
                        }

                    elif hasattr(boundary, 'edges'):
                        edges_payload = []
                        for edge in boundary.edges:
                            if hasattr(edge, 'start') and hasattr(edge, 'end'):
                                edges_payload.append({
                                    'edge_type': 'line',
                                    'start': self._vec3_to_list(edge.start),
                                    'end': self._vec3_to_list(edge.end),
                                })
                            elif hasattr(edge, 'center') and hasattr(edge, 'radius') and hasattr(edge, 'start_angle') and hasattr(edge, 'end_angle'):
                                edges_payload.append({
                                    'edge_type': 'arc',
                                    'center': self._vec3_to_list(edge.center),
                                    'radius': float(edge.radius),
                                    'start_angle': float(edge.start_angle),
                                    'end_angle': float(edge.end_angle),
                                    'ccw': bool(getattr(edge, 'ccw', True)),
                                })

                        path_payload = {
                            'path_type': 'edge',
                            'edges': edges_payload,
                        }

                    if path_payload:
                        hatch_paths.append(path_payload)
            
            geometry = {
                'boundaries': boundaries,
                'hatch_paths': hatch_paths,
                'pattern_name': dxfentity.dxf.pattern_name if hasattr(dxfentity.dxf, 'pattern_name') else '',
                'solid_fill': dxfentity.dxf.solid_fill if hasattr(dxfentity.dxf, 'solid_fill') else False
            }
            entity.add_geometries(geometry)
        except:
            pass

    def _extract_leader_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """LEADER"""
        try:
            vertices = [self._vec3_to_list(v) for v in dxfentity.vertices()]
            geometry = {
                'vertices': vertices,
                'text': dxfentity.dxf.text if hasattr(dxfentity.dxf, 'text') else ''
            }
            entity.add_geometries(geometry)
        except:
            pass

    def _extract_ray_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """RAY"""
        geometry = {
            'start': self._vec3_to_list(dxfentity.dxf.start),
            'unit_vector': self._vec3_to_list(dxfentity.dxf.unit_vector)
        }
        entity.add_geometries(geometry)

    def _extract_xline_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """XLINE (infinite line)"""
        geometry = {
            'start': self._vec3_to_list(dxfentity.dxf.start),
            'unit_vector': self._vec3_to_list(dxfentity.dxf.unit_vector)
        }
        entity.add_geometries(geometry)

    def _extract_attrib_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """ATTRIB (block attribute)"""
        geometry = {
            'insert': self._vec3_to_list(dxfentity.dxf.insert),
            'tag': dxfentity.dxf.tag,
            'text': dxfentity.dxf.text,
            'color': getattr(dxfentity.dxf, 'color', None),
            'true_color': getattr(dxfentity.dxf, 'true_color', None),
            'transparency': getattr(dxfentity.dxf, 'transparency', None),
        }
        entity.add_geometries(geometry)
        entity.add_attributes({
            'tag': dxfentity.dxf.tag,
            'text': dxfentity.dxf.text
        })

    def _extract_shape_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """SHAPE"""
        geometry = {
            'insert': self._vec3_to_list(dxfentity.dxf.insert),
            'name': dxfentity.dxf.name,
            'size': dxfentity.dxf.size if hasattr(dxfentity.dxf, 'size') else 1.0
        }
        entity.add_geometries(geometry)
        entity.add_attributes({'name': dxfentity.dxf.name})

    def _extract_viewport_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """VIEWPORT"""
        geometry = {
            'center': self._vec3_to_list(dxfentity.dxf.center),
            'width': dxfentity.dxf.width,
            'height': dxfentity.dxf.height
        }
        entity.add_geometries(geometry)
        entity.add_attributes({
            'width': dxfentity.dxf.width,
            'height': dxfentity.dxf.height
        })

    def _extract_image_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """IMAGE"""
        geometry = {
            'insert': self._vec3_to_list(dxfentity.dxf.insert),
            'u_pixel': dxfentity.dxf.u_pixel,
            'v_pixel': dxfentity.dxf.v_pixel,
            'image_def_handle': dxfentity.dxf.image_def_handle if hasattr(dxfentity.dxf, 'image_def_handle') else None
        }
        entity.add_geometries(geometry)

    def _extract_imagedef_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """IMAGEDEF"""
        geometry = {
            'filename': dxfentity.dxf.filename if hasattr(dxfentity.dxf, 'filename') else ''
        }
        entity.add_geometries(geometry)

    def _extract_dimension_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """DIMENSION"""
        # Dimension - just store as is with all attributes
        pass

    def _extract_helix_data(self, dxfentity: EzDXFEntity, entity: DXFEntity):
        """HELIX"""
        try:
            geometry = {
                'base_point': self._vec3_to_list(dxfentity.dxf.base_point),
                'axis_vector': self._vec3_to_list(dxfentity.dxf.axis_vector),
                'radius': dxfentity.dxf.radius,
                'turns': dxfentity.dxf.turns,
                'height': dxfentity.dxf.height
            }
            entity.add_geometries(geometry)
            entity.add_attributes({
                'radius': dxfentity.dxf.radius,
                'turns': dxfentity.dxf.turns,
                'height': dxfentity.dxf.height
            })
        except:
            pass

    def save_svg_preview(
        self,
        filepath: str,
        output_dir: str,
        filename: str = "",
    ) -> Result[str]:
        if not filepath:
            return Result.fail("Empty filepath")

        try:
            os.makedirs(output_dir, exist_ok=True)

            drawing = ezdxf.readfile(filepath)
            msp = drawing.modelspace()

            stem = os.path.splitext(filename or os.path.basename(filepath))[0]
            preview_path = os.path.join(output_dir, f"{stem}.svg")

            backend = svg.SVGBackend()
            Frontend(RenderContext(drawing), backend).draw_layout(msp)

            with open(preview_path, "wt", encoding="utf-8") as preview_file:
                preview_file.write(backend.get_string(layout.Page(0, 0)))

            return Result.success(preview_path)
        except Exception as e:
            return Result.fail(f"Failed to save SVG preview: {e}")
