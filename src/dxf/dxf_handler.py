import ezdxf
from ezdxf import select
from ezdxf.entities import EdgeType, BoundaryPaths, BoundaryPathType, EdgePath
from ezdxf.layouts.layout import Modelspace, Paperspace
from ezdxf.document import Drawing
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing import layout, svg

import os

from ..logger.logger import Logger
from PyQt5.QtCore import  pyqtSignal, QObject
from qgis.core import QgsProject, QgsLayerTreeGroup

def get_first_visible_group():
    layer_tree = QgsProject.instance().layerTreeRoot()
    for child in layer_tree.children():
        if isinstance(child, QgsLayerTreeGroup) and child.isVisible():
            group_name = child.name()
            if ".dxf" in group_name:
                # Отрезаем всё, что идёт после ".dxf"
                dxf_name = group_name.split(".dxf")[0] + ".dxf"
                return dxf_name
    return None

def get_selected_file(tree_widget_handler):
    """Получает имя выбранного файла из TreeWidgetHandler"""
    return tree_widget_handler.get_selected_file_name()

def export_svg(doc, msp):
    backend = svg.SVGBackend()
    Frontend(RenderContext(doc), backend).draw_layout(msp)

    with open("../dxf_examples/your.svg", "wt") as fp:
        fp.write(backend.get_string(layout.Page(0, 0)))


class DXFHandler(QObject):
    progressChanged = pyqtSignal(int)

    def __init__(self, type_shape, type_selection, tree_widget_handler):
        super().__init__()
        self.msps: dict[str, Modelspace] = {}
        self.paper_space: dict[str, Paperspace] = {}
        self.dxf: dict[str, Drawing] = {}
        self.file_is_open = False
        self.type_shape = type_shape
        self.type_selection = type_selection
        self.tree_widget_handler = tree_widget_handler

    def read_dxf_file(self, file_name):
        """
        Reads a DXF file and returns a dictionary groupby layer.
        """
        try:
            fn = os.path.basename(file_name)
            self.dxf[fn] = ezdxf.readfile(file_name)
            #export_svg(self.dxf[fn], self.dxf[fn].modelspace())
            #self.dxf[fn].audit()
            msp = self.dxf[fn].modelspace()

           # block = self.dxf[fn].layouts_and_blocks()
            #Logger.log_message(f'Заголовки: {self.dxf[fn].header.varnames()} ')
            self.msps[fn] = msp

            self.file_is_open = True

            self.process_entities(msp)
            Logger.log_message(f"File {fn} successfully read.")
            # Get all entities grouped by layer
            layers_entities = msp.groupby(dxfattrib="layer")

            return layers_entities, fn


        except IOError:
            Logger.log_message(f"File {file_name} not found or could not be read.")
            self.file_is_open = False
        except ezdxf.DXFStructureError:
            Logger.log_message(f"Invalid DXF file format: {file_name}")
            self.file_is_open = False
        return None

    def select_entities_in_area(self, *args):
        """
        Select entities within the specified area based on the selection type.
        :param args: Parameters for the shape (coordinates, center point, radius, etc.).
        """
        # Map selection types to selection functions
        selection_functions = {
            'inside': select.bbox_inside,
            'outside': select.bbox_outside,
            'overlap': select.bbox_overlap
        }

        if self.type_selection.currentText() not in selection_functions:
            raise ValueError(f"Unsupported selection type: {self.type_selection.currentText()}")

        # Map shape types to shape creation functions
        shape_creators = {
            'rect': lambda x_min, x_max, y_min, y_max: select.Window((x_min, y_min), (x_max, y_max)),
            'circle': lambda center_point, radius: select.Circle(center_point, radius),
            'polygon': lambda points: select.Polygon(points)
        }

        if self.type_shape.currentText() not in shape_creators:
            raise ValueError(f"Unsupported shape type: {self.type_shape.currentText()}")

        # Create the shape object
        shape_obj = shape_creators[self.type_shape.currentText()](*args)

        # Get the appropriate selection function
        selection_func = selection_functions[self.type_selection.currentText()]
        Logger.log_message(self.tree_widget_handler)
        active_layer = get_selected_file(self.tree_widget_handler)
        if active_layer:
            Logger.log_message(f"Активный файл: {active_layer}")
        else:
            Logger.log_warning("Файл не выбран. Пожалуйста, выберите файл в дереве.")
            return []

        entities = list(selection_func(shape_obj, self.msps[active_layer]))

        self.process_entities(entities)
        return entities

    # TODO: пустышка для видимости прогресса (возможно получится подвязать к реальному прогрессу)
    def process_entities(self, entities):
        total_entities = len(entities)
        for i, entity in enumerate(entities):
            # Simulate processing of each entity
            progress = int((i + 1) / total_entities * 100)
            self.progressChanged.emit(progress)

    def get_layers(self, filename=None) -> dict:
        """
        Возвращает словарь с именами слоёв и списком сущностей на каждом слое.
        """
        if filename is None:
            filename = next(iter(self.dxf))

        if filename in self.msps:
            return self.msps[filename].groupby(dxfattrib="layer")
        else:
            return {} 
    
    def get_file_metadata(self, filename: str) -> dict:
        """
        Извлекает все доступные метаданные из DXF файла.
        """
        if filename not in self.dxf:
            Logger.log_error(f'DXF файл {filename} не загружен.')
            return {}

        drawing = self.dxf[filename]
        # Список заголовков файла
        headers_list = list(drawing.header.varnames())
        headers_dict = {h: drawing.header.get(h, None) for h in headers_list}

        # Заголовки файла (headers)
        file_metadata = {
            "headers": headers_dict,
            "version": drawing.dxfversion,
        }

        # Составляем итоговую структуру
        return {
            "file_metadata": file_metadata
        }

    def get_layer_metadata(self, filename: str, layer_name: str) -> dict:
        """
        Извлекает все доступные метаданные слоя DXF-файла.
        
        :param filename: Имя DXF-файла.
        :param layer_name: Имя слоя, для которого извлекаются метаданные.
        :return: Словарь с метаданными слоя.
        """
        # Проверяем, загружен ли файл
        dxf_file = self.dxf.get(filename)
        if not dxf_file:
            Logger.log_error(f"Файл {filename} не найден в DXFHandler.")
            return {"error": f"Файл {filename} не найден."}
        
        # Проверяем существование слоя
        layer = dxf_file.layers.get(layer_name)
        if not layer:
            Logger.log_error(f"Слой {layer_name} не найден в файле {filename}.")
            return {"error": f"Слой {layer_name} не найден."}

        # Основные свойства слоя
        layer_metadata = {
            "name": layer.dxf.name,
            "color": layer.dxf.color,
            "linetype": layer.dxf.linetype,
            "is_off": layer.is_off(),
            "is_frozen": layer.is_frozen(),
            "is_locked": layer.is_locked(),
            "plot": layer.dxf.plot,
            "lineweight": layer.dxf.lineweight,
        }


        return layer_metadata

    def get_tables(self, filename: str) -> dict:
        """
        Извлекает таблицы из DXF файла с использованием ezdxf.
        Возвращает словарь с именами таблиц и списком их записей.
        """
        if filename not in self.dxf:
            Logger.log_error(f"DXF файл {filename} не загружен.")
            return {"error": f"DXF файл {filename} не загружен."}

        drawing = self.dxf[filename]
        tables_info = {}
        # Маппинг стандартных таблиц DXF к именам атрибутов в ezdxf
        table_mapping = {
            'APPID': 'appid',
            'BLOCK_RECORD': 'block_record',
            'DIMSTYLE': 'dimstyle',
            'LAYER': 'layer',
            'LTYPE': 'linetype',
            'STYLE': 'style',
            'UCS': 'ucs',
            'VIEW': 'view',
            'VPORT': 'vport'
        }
        for name, attr_name in table_mapping.items():
            table = getattr(drawing.tables, attr_name, None)
            if table is None:
                continue
            records = []
            for record in table:
                records.append(record.dxfattribs())
            tables_info[name] = records

        return {"tables": tables_info}

    def extract_blocks_from_dxf(self, filename: str) -> list:
        """
        Извлекает блоки из DXF-файла и возвращает список блоков с их содержимым.
        
        """
        doc = self.dxf[filename]

        blocks_data = []

        for block in doc.blocks:
            block_info = {
                "name": block.name,
                "base_point": tuple(block.base_point),
                "entities": []
            }

            for entity in block:
                entity_data = {
                    "type": entity.dxftype(),
                    "handle": entity.dxf.handle,
                    "layer": entity.dxf.layer,
                }
                if hasattr(entity, 'dxf'):  # Извлекаем основные атрибуты
                    entity_data.update({attr: getattr(entity.dxf, attr, None) for attr in entity.dxf.all_existing_dxf_attribs()})

                # Специальная обработка LWPOLYLINE
                if entity.dxftype() == 'LWPOLYLINE':
                    entity : ezdxf.entities.LWPolyline
                    points = list(entity.get_points(format='xy'))  # Сохраняем только x, y
                    entity_data["points"] = points
                    entity_data["closed"] = entity.is_closed
                # Специальная обработка 3DSOLID
                elif entity.dxftype() == '3DSOLID':
                    entity : ezdxf.entities.Solid3d
                    try:
                        acis_data = entity.acis_data
                        entity_data["acis_data"] = acis_data  # raw ACIS data
                    except Exception as e:
                        entity_data["acis_error"] = str(e)
                # Специальная обработка HATCH
                elif entity.dxftype() == 'HATCH':
                    try:
                        boundary_paths = []
                        entity : ezdxf.entities.Hatch

                        for path in entity.paths:
                            path_data = {
                                "path_type": path.path_type_flags,
                                "edges": []
                            }
                            if entity.paths.has_edge_paths:
                                for edge in path.edges:
                                    if edge.type == EdgeType.LINE:
                                        path_data["edges"].append({
                                            "type": "LINE",
                                            "start": (edge.start[0], edge.start[1]),
                                            "end": (edge.end[0], edge.end[1])                                        })
                                    elif edge.type == EdgeType.ARC:
                                        path_data["edges"].append({
                                            "type": "ARC",
                                            "center": (edge.center[0], edge.center[1]),
                                            "radius": edge.radius,
                                            "start_angle": edge.start_angle,
                                            "end_angle": edge.end_angle,
                                            "ccw": edge.ccw
                                        })
                                    elif edge.type == EdgeType.ELLIPSE:
                                        path_data["edges"].append({
                                            "type": "ELLIPSE",
                                            "center": (edge.center[0], edge.center[1]),
                                            "major_axis": (edge.major_axis[0], edge.major_axis[1]),
                                            "ratio": edge.ratio,
                                            "start_param": edge.start_param,
                                            "end_param": edge.end_param,
                                            "ccw": edge.ccw
                                        })
                                    elif edge.type == EdgeType.SPLINE:
                                        control_points = [(p[0], p[1]) for p in edge.control_points]
                                        path_data["edges"].append({
                                            "type": "SPLINE",
                                            "degree": edge.degree,
                                            "control_points": control_points,
                                            "fit_points": [(p[0], p[1]) for p in edge.fit_points],
                                            "knot_values": edge.knot_values,
                                            "weights": edge.weights,
                                            "periodic": edge.periodic,
                                            "start_tangent": (edge.start_tangent[0], edge.start_tangent[1]),
                                            "end_tangent": (edge.end_tangent[0], edge.end_tangent[1]),
                                        })
                            else:# entity.paths.type == BoundaryPathType.POLYLINE:
                                vertices = [(v[0], v[1], v[2]) for v in path.vertices]
                                path_data["edges"].append({
                                    "type": "POLYLINE",
                                    "vertices": vertices,
                                    "is_closed": path.is_closed
                                })
                            boundary_paths.append(path_data)
                        entity_data["boundary_paths"] = boundary_paths
                    except Exception as e:
                        Logger.log_error(f"HATCH processing error: {e}")
                block_info["entities"].append(entity_data)
            blocks_data.append(block_info)

        return blocks_data
    def extract_all_xrecords(self, filename):
        """
        Извлекает все XRECORD объекты из DXF файла.

        Функция ищет XRECORD объекты в секции OBJECTS и в extension dictionaries графических объектов.
        """
        doc = self.dxf[filename]
        xrecords = {
            "objects": [],
            "entity": {}
        }


        # Ищем XRECORD объекты в секции OBJECTS
        for obj in doc.objects:
            if obj.dxftype() == "XRECORD":
                xrecords["objects"].append(obj)
        
        # Ищем XRECORD объекты в extension dictionaries графических объектов (например, в Modelspace)
        msp = doc.modelspace()
        for entity in msp:
            if entity.has_extension_dict:
                xdict = entity.get_extension_dict()
                for key, obj in xdict.items():
                    if obj.dxftype() == "XRECORD":
                        if entity.dxf.handle not in xrecords["entity"]:
                            xrecords["entity"][entity.dxf.handle] = []
                        xrecords["entity"][entity.dxf.handle].append(obj)
        
        return xrecords

    # Новый метод для извлечения объектов Dictionary из DXF файла
    def extract_dictionary(self, filename: str) -> dict:
        """
        Извлекает все Dictionary объекты из DXF файла.
        
        Возвращает:
            dict с ключами в виде handle словаря, значениями - информация об объекте Dictionary и его записях.
        """
        if filename not in self.dxf:
            Logger.log_error(f"DXF файл {filename} не загружен.")
            return {}
        
        doc = self.dxf[filename]
        dictionaries = {}
        for obj in doc.objects:
            if obj.dxftype() in ("DICTIONARY", "ACDBDICTIONARYWDFLT"):
                # Собираем базовую информацию о словаре
                dictionary_info = {
                    "type": obj.dxftype(),
                    "hard_owned": getattr(obj.dxf, "hard_owned", None),
                    "cloning": getattr(obj.dxf, "cloning", None),
                    "entries": {}
                }
                # Итерируем по записям словаря
                try:
                    for key, value in obj.items():
                        dictionary_info["entries"][key] = value  # значение может быть handle строкой или DXFEntity
                except Exception as e:
                    Logger.log_error(f"Ошибка при извлечении записей словаря с handle {obj.dxf.handle}: {e}")
                dictionaries[obj.dxf.handle] = dictionary_info

        return dictionaries

    # Новый метод для извлечения объектов DictionaryVar и DictionaryWithDefault из DXF файла
    def extract_dictionary_vars_and_with_default(self, filename: str) -> dict:
        """
        Извлекает объекты DictionaryVar и DictionaryWithDefault из DXF файла.

        Возвращает:
            dict с ключами:
                "dictionary_vars" - список словарных переменных,
                "dictionary_with_default" - список объектов DictionaryWithDefault.
        """
        if filename not in self.dxf:
            Logger.log_error(f"DXF файл {filename} не загружен.")
            return {}
        
        doc = self.dxf[filename]
        dictionary_vars = []
        dictionary_with_default = []
        
        for obj in doc.objects:
            if obj.dxftype() == "DICTIONARYVAR":
                var_info = {
                    "handle": obj.dxf.handle,
                    "schema": getattr(obj.dxf, "schema", None),
                    "value": getattr(obj.dxf, "value", None),
                    "propertyvalue": obj.propertyvalue if hasattr(obj, "propertyvalue") else None
                }
                dictionary_vars.append(var_info)
            elif obj.dxftype() == "ACDBDICTIONARYWDFLT":
                # Собираем default, если он существует
                dwd_info = {
                    "handle": obj.dxf.handle,
                    "default": getattr(obj.dxf, "default", None)
                }
                dictionary_with_default.append(dwd_info)
        
        return {
            "dictionary_vars": dictionary_vars,
            "dictionary_with_default": dictionary_with_default
        }

