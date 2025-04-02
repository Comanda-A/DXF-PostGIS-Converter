import ezdxf
from ezdxf import select
from ezdxf.entities import EdgeType
from ezdxf.layouts.layout import Modelspace, Paperspace
from ezdxf.document import Drawing
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing import layout, svg

import os

from ..logger.logger import Logger
from PyQt5.QtCore import  pyqtSignal, QObject, Qt
from ..localization.localization_manager import LocalizationManager

def get_selected_file(tree_widget_handler):
    """
    Получает имя выбранного файла из TreeWidgetHandler.
    """
    return tree_widget_handler.get_selected_file_name()

class DXFHandler(QObject):
    """
    Обработчик DXF файлов. Управляет чтением, обработкой и извлечением данных из DXF файлов.
    """
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
        self.selected_entities = {}
        self.localization = LocalizationManager.instance()
        if self.tree_widget_handler is not None:
            self.tree_widget_handler.selection_changed.connect(self.update_selected_entities)

    def update_selected_entities(self, file_name=None):
        """
        Обновляет selected_entities на основе выбранных элементов в дереве
        """
        if file_name is None:
            file_name = self.tree_widget_handler.get_selected_file_name()
            if not file_name:
                return

        if file_name not in self.msps:
            return

        selected_entities = []
        
        # Получаем все слои из файла
        layers = self.msps[file_name].groupby(dxfattrib="layer")
        
        # Для каждого слоя проверяем выбранные сущности
        for layer_name, entities in layers.items():
            if file_name in self.tree_widget_handler.tree_items:
                layer_data = self.tree_widget_handler.tree_items[file_name].get(layer_name)
                if layer_data:
                    # Проверяем каждую сущность в слое
                    for entity in entities:
                        entity_description = f"{entity}"
                        entity_item = layer_data['entities'].get(entity_description)
                        if entity_item and entity_item.checkState(0) == Qt.Checked:
                            selected_entities.append(entity)

        # Обновляем selected_entities для данного файла
        self.selected_entities[file_name] = selected_entities
        Logger.log_message(f"Updated selected entities for {file_name}: {len(selected_entities)} entities")

    def get_file_path(self, filename):
        """
        Возвращает полный путь к файлу.
        """
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dxf', filename)

    @staticmethod
    def save_svg_preview(doc, msp, filename):
        """
        Сохраняет SVG превью DXF файла.
        Возвращает путь к сохраненному SVG файлу.
        """
        try:
            # Создаем директорию превью в корне плагина
            preview_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'previews')
            os.makedirs(preview_dir, exist_ok=True)

            # Генерируем уникальное имя файла для превью
            preview_filename = f"{os.path.splitext(os.path.basename(filename))[0]}.svg"
            preview_path = os.path.join(preview_dir, preview_filename)

            Logger.log_message(f"Сохранение превью в: {preview_path}")

            backend = svg.SVGBackend()
            Frontend(RenderContext(doc), backend).draw_layout(msp)

            with open(preview_path, "wt") as fp:
                fp.write(backend.get_string(layout.Page(0, 0)))

            Logger.log_message(f"Превью успешно сохранено в: {preview_path}")
            return preview_path

        except Exception as e:
            Logger.log_error(f"Ошибка сохранения SVG превью: {str(e)}")
            return None

    def read_dxf_file(self, file_name):
        """
        Читает DXF файл и возвращает словарь сущностей, сгруппированных по слоям.
        """
        try:
            fn = os.path.basename(file_name)
            self.dxf[fn] = ezdxf.readfile(file_name)
            msp = self.dxf[fn].modelspace()
            self.msps[fn] = msp
            self.file_is_open = True

            self.process_entities(msp)
            Logger.log_message(f"Файл {fn} успешно прочитан.")
            # Получаем все сущности, сгруппированные по слоям
            layers_entities = msp.groupby(dxfattrib="layer")

            return layers_entities, fn

        except IOError:
            Logger.log_message(f"Файл {file_name} не найден или не может быть прочитан.")
            self.file_is_open = False
        except ezdxf.DXFStructureError:
            Logger.log_message(f"Неверный формат DXF файла: {file_name}")
            self.file_is_open = False
        return None

    def select_entities_in_area(self, *args):
        """
        Выбирает сущности в указанной области в зависимости от типа выделения.
        :param args: Параметры для фигуры (координаты, центральная точка, радиус и т.д.).
        """
        ui = self.localization.strings.UI
        
        # Соответствие типов выделения функциям выбора
        selection_functions = {
            ui["selection_inside"]: select.bbox_inside,
            ui["selection_outside"]: select.bbox_outside,
            ui["selection_intersect"]: select.bbox_overlap
        }

        selection_type = self.type_selection.currentText()
        if selection_type not in selection_functions:
            raise ValueError(f"Unsupported selection type: {selection_type}")

        # Соответствие типов фигур функциям создания
        shape_creators = {
            ui["shape_rectangle"]: lambda x_min, x_max, y_min, y_max: select.Window((x_min, y_min), (x_max, y_max)),
            ui["shape_circle"]: lambda center_point, radius: select.Circle(center_point, radius),
            ui["shape_polygon"]: lambda points: select.Polygon(points)
        }

        shape_type = self.type_shape.currentText()
        if shape_type not in shape_creators:
            raise ValueError(f"Unsupported shape type: {shape_type}")

        # Создаем объект фигуры
        shape_obj = shape_creators[shape_type](*args)

        # Получаем соответствующую функцию выбора
        selection_func = selection_functions[selection_type]
        Logger.log_message(self.tree_widget_handler)
        active_layer = get_selected_file(self.tree_widget_handler)
        if active_layer:
            Logger.log_message(f"Активный файл: {active_layer}")
        else:
            Logger.log_warning("Файл не выбран. Пожалуйста, выберите файл в дереве.")
            return []

        entities = list(selection_func(shape_obj, self.msps[active_layer]))
        
        # Store selected entities for the active file
        self.selected_entities[active_layer] = entities

        self.process_entities(entities)
        return entities

    def get_entities_for_export(self, filename):
        """
        Возвращает список сущностей для экспорта в базу данных.
        Если есть выбранные сущности - возвращает их, иначе все сущности файла.
        """
        if filename in self.selected_entities and self.selected_entities[filename]:
            return self.selected_entities[filename]
        return self.msps[filename].groupby(dxfattrib="layer") if filename in self.msps else []

    def clear_selection(self, filename=None):
        """
        Очищает выбранные сущности для указанного файла или для всех файлов.
        """
        if filename:
            self.selected_entities.pop(filename, None)
        else:
            self.selected_entities.clear()

    def process_entities(self, entities):
        """
        Обрабатывает сущности и отправляет сигнал о прогрессе.
        Временная заглушка для демонстрации прогресса.
        """
        total_entities = len(entities)
        for i, entity in enumerate(entities):
            # Имитация обработки каждой сущности
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
        Извлекает таблицы из DXF файла.
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
    def simle_read_dxf_file(self, file_name):
        """
        Читает DXF файл и возвращает объект Drawing.
        """
        doc = ezdxf.readfile(file_name)
        return doc
    def extract_blocks_from_dxf(self, filename: str) -> list:
        """
        Извлекает блоки из DXF-файла и возвращает список блоков с их содержимым.
        Если есть выбранные сущности, извлекает только блоки, связанные с этими сущностями.
        """
        try:
            doc = self.dxf[filename]

            blocks_data = []
            
            # Определяем, есть ли выбранные сущности
            selected_entities = self.selected_entities.get(filename, [])
            
            # Если есть выбранные сущности, собираем список используемых блоков
            used_block_names = set()
            if selected_entities:
                for entity in selected_entities:
                    # Проверяем, является ли сущность вставкой блока
                    if entity.dxftype() == 'INSERT':
                        used_block_names.add(entity.dxf.name)
                    # Проверяем наличие вложенных блоков
                    if hasattr(entity, 'virtual_entities'):
                        for virtual_entity in entity.virtual_entities():
                            if virtual_entity.dxftype() == 'INSERT':
                                used_block_names.add(virtual_entity.dxf.name)

            # Обрабатываем блоки
            for block in doc.blocks:
                # Пропускаем блок, если есть выбранные сущности и блок не используется
                if selected_entities and block.name not in used_block_names:
                    continue

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
                    if hasattr(entity, 'dxf'):
                        entity_data.update({attr: getattr(entity.dxf, attr, None) 
                                        for attr in entity.dxf.all_existing_dxf_attribs()})

                    # Специальная обработка различных типов сущностей
                    if entity.dxftype() == 'LWPOLYLINE':
                        entity_data["points"] = list(entity.get_points(format='xy'))
                        entity_data["closed"] = entity.is_closed
                    elif entity.dxftype() == '3DSOLID':
                        try:
                            entity_data["acis_data"] = entity.acis_data
                        except Exception as e:
                            entity_data["acis_error"] = str(e)
                    elif entity.dxftype() == 'HATCH':
                        try:
                            boundary_paths = []
                            for path in entity.paths:
                                path_data = {
                                    "path_type": path.path_type_flags,
                                    "edges": []
                                }
                                if entity.paths.has_edge_paths:
                                    for edge in path.edges:
                                        edge_data = self._process_hatch_edge(edge)
                                        if edge_data:
                                            path_data["edges"].append(edge_data)
                                else:
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

        except Exception as e:
            Logger.log_error(f"Ошибка при извлечении блоков из DXF файла: {e}")
            return []

    def _process_hatch_edge(self, edge):
        """
        Вспомогательный метод для обработки рёбер штриховки.
        """
        if edge.type == EdgeType.LINE:
            return {
                "type": "LINE",
                "start": (edge.start[0], edge.start[1]),
                "end": (edge.end[0], edge.end[1])
            }
        elif edge.type == EdgeType.ARC:
            return {
                "type": "ARC",
                "center": (edge.center[0], edge.center[1]),
                "radius": edge.radius,
                "start_angle": edge.start_angle,
                "end_angle": edge.end_angle,
                "ccw": edge.ccw
            }
        elif edge.type == EdgeType.ELLIPSE:
            return {
                "type": "ELLIPSE",
                "center": (edge.center[0], edge.center[1]),
                "major_axis": (edge.major_axis[0], edge.major_axis[1]),
                "ratio": edge.ratio,
                "start_param": edge.start_param,
                "end_param": edge.end_param,
                "ccw": edge.ccw
            }
        elif edge.type == EdgeType.SPLINE:
            return {
                "type": "SPLINE",
                "degree": edge.degree,
                "control_points": [(p[0], p[1]) for p in edge.control_points],
                "fit_points": [(p[0], p[1]) for p in edge.fit_points],
                "knot_values": edge.knot_values,
                "weights": edge.weights,
                "periodic": edge.periodic,
                "start_tangent": (edge.start_tangent[0], edge.start_tangent[1]),
                "end_tangent": (edge.end_tangent[0], edge.end_tangent[1])
            }
        return None

    def extract_object_section(self, filename: str) -> dict:
        """
        Извлекает различные объекты из секции OBJECTS DXF файла.
        
        Включает:
        - XRECORD объекты
        - Dictionary объекты
        - DictionaryVar объекты
        - DictionaryWithDefault объекты
        
        Returns:
            dict: Словарь с информацией о различных объектах
        """
        if filename not in self.dxf:
            Logger.log_error(f"DXF файл {filename} не загружен.")
            return {}
        
        doc = self.dxf[filename]
        result = {
            "xrecords": {
                "objects": [],
                "entity": {}
            },
            "dictionaries": {},
            "dictionary_vars": [],
            "dictionary_with_default": []
        }

        def process_dictionary(dictionary, parent_handle=None):
            """
            Рекурсивно обрабатывает словари, включая вложенные, и добавляет их в результат.

            Args:
                dictionary: Текущий обрабатываемый словарь.
                parent_handle: Handle родительского словаря, если имеется.
            """
            dictionary_info = {
                "type": dictionary.dxftype(),
                "hard_owned": getattr(dictionary.dxf, "hard_owned", None),
                "cloning": getattr(dictionary.dxf, "cloning", None),
                "entries": {},
                "parent_handle": parent_handle
            }
            try:
                for key, value in dictionary.items():
                    if isinstance(value, str):
                        # Если значение - строка, это handle объекта
                        referenced_obj = doc.entitydb.get(value)
                        if referenced_obj:
                            value_info = {
                                "type": referenced_obj.dxftype(),
                                "handle": value
                            }
                            if referenced_obj.dxftype() in ("DICTIONARY", "ACDBDICTIONARYWDFLT"):
                                process_dictionary(referenced_obj, parent_handle=dictionary.dxf.handle)
                        else:
                            value_info = {
                                "type": "Unknown",
                                "handle": value
                            }
                    else:
                        value_info = {
                            "type": value.dxftype(),
                            "handle": value.dxf.handle
                        }
                        if value.dxftype() in ("DICTIONARY", "ACDBDICTIONARYWDFLT"):
                            process_dictionary(value, parent_handle=dictionary.dxf.handle)
                    dictionary_info["entries"][key] = value_info
            except Exception as e:
                Logger.log_error(f"Ошибка при извлечении записей словаря с handle {dictionary.dxf.handle}: {e}")
            result["dictionaries"][dictionary.dxf.handle] = dictionary_info

        # Обработка XRECORD объектов в секции OBJECTS
        for obj in doc.objects:
            if obj.dxftype() == "XRECORD":
                xrecord_data = {}
                for tag in obj.tags:
                    xrecord_data[tag.code] = tag.value
                result["xrecords"]["objects"].append({
                    "handle": obj.dxf.handle,
                    "data": xrecord_data
                })
            
            # Обработка Dictionary объектов
            elif obj.dxftype() in ("DICTIONARY", "ACDBDICTIONARYWDFLT"):
                process_dictionary(obj)
            
            # Обработка DictionaryVar объектов
            elif obj.dxftype() == "DICTIONARYVAR":
                var_info = {
                    "handle": obj.dxf.handle,
                    "schema": getattr(obj.dxf, "schema", None),
                    "value": getattr(obj.dxf, "value", None),
                    "propertyvalue": obj.propertyvalue if hasattr(obj, "propertyvalue") else None
                }
                result["dictionary_vars"].append(var_info)
            
            # Обработка DictionaryWithDefault объектов
            elif obj.dxftype() == "ACDBDICTIONARYWDFLT":
                dwd_info = {
                    "handle": obj.dxf.handle,
                    "default": getattr(obj.dxf, "default", None)
                }
                result["dictionary_with_default"].append(dwd_info)

        # Поиск XRECORD объектов в extension dictionaries графических объектов
        msp = doc.modelspace()
        for entity in msp:
            if entity.has_extension_dict:
                xdict = entity.get_extension_dict()
                for key, obj in xdict.items():
                    if obj.dxftype() == "XRECORD":
                        if entity.dxf.handle not in result["xrecords"]["entity"]:
                            result["xrecords"]["entity"][entity.dxf.handle] = []
                        xrecord_data = {}
                        for tag in obj.tags:
                            xrecord_data[tag.code] = tag.value
                        result["xrecords"]["entity"][entity.dxf.handle].append({
                            "handle": obj.dxf.handle,
                            "data": xrecord_data
                        })

        return result

    def extract_linetypes(self, filename: str) -> dict:
        """
        Извлекает информацию о типах линий из секции TABLES DXF-файла.

        Args:
            filename (str): Путь к DXF-файлу.

        Returns:
            dict: Словарь с информацией о типах линий, где ключи — имена типов линий,
                  а значения — их описания и паттерны.
        """
        if filename not in self.dxf:
            Logger.log_error(f"DXF файл {filename} не загружен.")
            return {}

        doc = self.dxf[filename]
        linetypes = {}
        for linetype in doc.linetypes:
            pattern_values = []
            for tag in linetype.pattern_tags.tags:
                if tag.code == 49:  # Код группы 49 соответствует элементам паттерна
                    pattern_values.append(tag.value)
            linetypes[linetype.dxf.name] = {
                "description": linetype.dxf.description,
                "pattern": pattern_values
            }
        return linetypes

    def extract_styles(self, filename: str) -> dict:
        """
        Извлекает стили из DXF файла.
        """
        self.filename = filename
        doc = self.dxf[filename]
        styles = {}
        for style in doc.styles:
            styles[style.dxf.name] = style.dxfattribs()
        Logger.log_message(f"Извлечены стили: {styles}")
        return styles
    def get_entity_db(self, handle):
        """
        Возвращает сущность из базы данных по указанному handle.
        """
        doc = self.dxf[self.filename]
        mleader_style = doc.entitydb.get(handle)
        return mleader_style

