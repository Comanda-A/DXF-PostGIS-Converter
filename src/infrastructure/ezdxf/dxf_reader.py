
import os
import ezdxf
from ezdxf.entities import DXFEntity as EzDXFEntity
from ...domain.value_objects import Result, DxfEntityType
from ...domain.entities import DXFDocument, DXFContent, DXFLayer, DXFEntity
from ...domain.services import IDXFReader

class DXFReader(IDXFReader):

    _GEOMETRIES = {
        'LINE': ["start", "end"],
        'POINT': ["location"],
        'CIRCLE': ["center", "radius"],
        'ARC': ["center", "radius", "start_angle", "end_angle"],
        'ELLIPSE': ["center", "major_axis", "extrusion", "ratio", "start_param", "end_param"],
        'SPLINE': ["degree"],
        'INSERT': ["name", "insert", "xscale", "yscale", "zscale", "rotation", "row_count", "row_spacing", "column_count", "column_spacing"],
        '3DSOLID': ["history_handle"],
        '3DFACE': ["vtx0", "vtx1", "vtx2", "vtx3", "invisible_edges"],
        'LWPOLYLINE': ["elevation", "flags", "const_width", "count"],
        'MULTILEADER': ["arrow_head_handle", "arrow_head_size", "block_color", "block_connection_type", "block_record_handle", "block_rotation", "block_scale_vector", "content_type", "dogleg_length", "has_dogleg", "has_landing", "has_text_frame", "is_annotative", "is_text_direction_negative", "leader_extend_to_text", "leader_line_color"],
        'TEXT': ["text", "insert", "align_point", "height", "rotation", "oblique", "style", "width", "halign", "valign", "text_generation_flag"],
        'ATTRIB': ["tag", "text", "is_invisible", "is_const", "is_verify", "is_preset", "has_embedded_mtext_entity"],
        'BODY': ["version", "flags", "uid", "acis_data", "sat", "has_binary_data"],
        'ARC_DIMENSION': ["defpoint2", "defpoint3", "defpoint4", "start_angle", "end_angle", "is_partial", "has_leader", "leader_point1", "leader_point2", "dimtype"],
        'HATCH': ["pattern_name", "solid_fill", "associative", "hatch_style", "pattern_type", "pattern_angle", "pattern_scale", "pattern_double", "n_seed_points", "elevation"],
        'HELIX': ["axis_base_point", "start_point", "axis_vector", "radius", "turn_height", "turns", "handedness", "constrain"],
        'IMAGE': ["insert", "u_pixel", "v_pixel", "image_size", "image_def_handle", "flags", "clipping", "brightness", "contrast", "fade", "clipping_boundary_type", "count_boundary_points", "clip_mode", "boundary_path", "image_def"]
    }

    def open(self, filepath: str) -> Result[DXFDocument]:
        try:
            # Открываем DXF файл с помощью ezdxf и выполняем базовую проверку
            drawing = ezdxf.readfile(filepath)
            drawing.audit()
            msp = drawing.modelspace()

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
                    # Добавляем атрибуты сущности
                    entity.add_attributes(dxfentity.dxfattribs())
                    # Добавляем геометрические данные сущности, если они поддерживаются
                    if dxfentity.dxftype() in DXFReader._GEOMETRIES:
                        geometry = {prop: getattr(dxfentity.dxf, prop) for prop in DXFReader._GEOMETRIES[dxfentity.dxftype()]}
                        entity.add_geometries(geometry)
                    # Добавляем сущность в слой
                    layer.add_entities([entity])

            return Result.success(doc)
        except Exception as e:
            return Result.fail(f"Failed to open DXF file: {str(e)}")
