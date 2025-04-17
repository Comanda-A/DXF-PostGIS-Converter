import ezdxf
from ezdxf import select
from ezdxf.layouts.layout import Modelspace, Paperspace
from ezdxf.document import Drawing
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing import layout, svg

import os

from ..logger.logger import Logger
from PyQt5.QtCore import pyqtSignal, QObject, Qt
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
        self.file_paths: dict[str, str] = {}
        self.file_is_open = False
        self.type_shape = type_shape
        self.type_selection = type_selection
        self.tree_widget_handler = tree_widget_handler
        self.selected_entities = {}
        self.len_entities_file = {}
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
        return self.file_paths.get(filename, None)

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
            self.file_paths[fn] = file_name
            self.dxf[fn] = ezdxf.readfile(file_name)
            self.dxf[fn].audit()
            msp = self.dxf[fn].modelspace()
            self.msps[fn] = msp
            self.file_is_open = True

            self.process_entities(msp)
            Logger.log_message(f"Файл {fn} успешно прочитан.")
            # Получаем все сущности, сгруппированные по слоям
            layers_entities = msp.groupby(dxfattrib="layer")
            self.len_entities_file[fn] = sum(len(v) for v in layers_entities.values())
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

    def get_entities_for_export(self, filename) -> dict:
        """
        Возвращает словарь сущностей для экспорта в базу данных, сгруппированных по слоям.
        Если есть выбранные сущности - возвращает их сгруппированными по слоям, иначе все сущности файла.
        """
        if filename not in self.msps:
            Logger.log_warning(f"Файл {filename} не найден в загруженных файлах")
            return {}
            
        # Если есть выбранные сущности, группируем их по слоям
        if filename in self.selected_entities and self.selected_entities[filename]:
            layers_entities = {}
            for entity in self.selected_entities[filename]:
                layer_name = entity.dxf.layer
                if layer_name not in layers_entities:
                    layers_entities[layer_name] = []
                layers_entities[layer_name].append(entity)
            return layers_entities
        return self.msps[filename].groupby(dxfattrib="layer") if filename in self.msps else []

    def simle_read_dxf_file(self, file_name):
        """
        Читает DXF файл и возвращает объект Drawing.
        """
        doc = ezdxf.readfile(file_name)
        return doc
