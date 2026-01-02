# -*- coding: utf-8 -*-
"""
DXF Handler - работа с DXF файлами (Domain Layer).

Обёртка над ezdxf для работы с DXF документами.
Не содержит UI-зависимостей.
"""

import os
from typing import Dict, Optional, List, Any, Callable

import ezdxf
from ezdxf import select
from ezdxf.layouts.layout import Modelspace, Paperspace
from ezdxf.document import Drawing
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing import layout, svg
from ezdxf import xref
from ezdxf.xref import ConflictPolicy

from ...logger.logger import Logger


class DXFHandlerCore:
    """
    Обработчик DXF файлов (без UI-зависимостей).
    
    Содержит чистую бизнес-логику работы с DXF файлами.
    Для UI-версии см. src/dxf/dxf_handler.py
    """
    
    def __init__(self):
        """Инициализация обработчика."""
        self.msps: Dict[str, Modelspace] = {}
        self.paper_space: Dict[str, Paperspace] = {}
        self.dxf: Dict[str, Drawing] = {}
        self.file_paths: Dict[str, str] = {}
        self.file_is_open = False
        self.selected_entities: Dict[str, List[Any]] = {}
        self.len_entities_file: Dict[str, int] = {}
    
    def get_file_path(self, filename: str) -> Optional[str]:
        """
        Возвращает полный путь к файлу.
        
        Args:
            filename: Имя файла
            
        Returns:
            Полный путь или None
        """
        return self.file_paths.get(filename, None)
    
    @staticmethod
    def save_svg_preview(doc: Drawing, msp: Modelspace, filename: str) -> Optional[str]:
        """
        Сохраняет SVG превью DXF файла.
        
        Args:
            doc: DXF документ
            msp: Modelspace документа
            filename: Путь к файлу для генерации имени превью
            
        Returns:
            Путь к сохраненному SVG файлу или None
        """
        try:
            # Создаем директорию превью в корне плагина
            preview_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 
                'previews'
            )
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
    
    def read_dxf_file(self, file_name: str, progress_callback: Optional[Callable[[int], None]] = None):
        """
        Читает DXF файл и возвращает словарь сущностей, сгруппированных по слоям.
        
        Args:
            file_name: Путь к DXF файлу
            progress_callback: Опциональный callback для прогресса
            
        Returns:
            Кортеж (layers_entities, filename) или None при ошибке
        """
        try:
            fn = os.path.basename(file_name)
            self.file_paths[fn] = file_name
            self.dxf[fn] = ezdxf.readfile(file_name)
            self.dxf[fn].audit()
            msp = self.dxf[fn].modelspace()
            self.msps[fn] = msp
            self.file_is_open = True

            if progress_callback:
                self._process_entities_with_callback(msp, progress_callback)
            
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
    
    def _process_entities_with_callback(
        self, 
        entities, 
        progress_callback: Callable[[int], None]
    ):
        """
        Обрабатывает сущности с callback для прогресса.
        
        Args:
            entities: Итерируемый объект сущностей
            progress_callback: Callback с процентом (0-100)
        """
        entities_list = list(entities)
        total_entities = len(entities_list)
        for i, entity in enumerate(entities_list):
            progress = int((i + 1) / total_entities * 100)
            progress_callback(progress)
    
    def select_entities_in_area(
        self,
        filename: str,
        shape_type: str,
        selection_type: str,
        *args
    ) -> List[Any]:
        """
        Выбирает сущности в указанной области.
        
        Args:
            filename: Имя файла для выборки
            shape_type: Тип фигуры ('rectangle', 'circle', 'polygon')
            selection_type: Тип выделения ('inside', 'outside', 'intersect')
            *args: Параметры для фигуры
            
        Returns:
            Список выбранных сущностей
        """
        if filename not in self.msps:
            Logger.log_warning(f"Файл {filename} не найден")
            return []
        
        # Соответствие типов выделения функциям выбора
        selection_functions = {
            'inside': select.bbox_inside,
            'outside': select.bbox_outside,
            'intersect': select.bbox_overlap
        }
        
        if selection_type not in selection_functions:
            raise ValueError(f"Unsupported selection type: {selection_type}")
        
        # Соответствие типов фигур функциям создания
        shape_creators = {
            'rectangle': lambda x_min, x_max, y_min, y_max: select.Window((x_min, y_min), (x_max, y_max)),
            'circle': lambda center_point, radius: select.Circle(center_point, radius),
            'polygon': lambda points: select.Polygon(points)
        }
        
        if shape_type not in shape_creators:
            raise ValueError(f"Unsupported shape type: {shape_type}")
        
        # Создаем объект фигуры
        shape_obj = shape_creators[shape_type](*args)
        
        # Получаем соответствующую функцию выбора
        selection_func = selection_functions[selection_type]
        
        entities = list(selection_func(shape_obj, self.msps[filename]))
        
        # Сохраняем выбранные сущности
        self.selected_entities[filename] = entities
        
        return entities
    
    def set_selected_entities(self, filename: str, entities: List[Any]):
        """
        Устанавливает выбранные сущности для файла.
        
        Args:
            filename: Имя файла
            entities: Список сущностей
        """
        self.selected_entities[filename] = entities
    
    def clear_selection(self, filename: Optional[str] = None):
        """
        Очищает выбранные сущности.
        
        Args:
            filename: Имя файла (если None, очищает все)
        """
        if filename:
            self.selected_entities.pop(filename, None)
        else:
            self.selected_entities.clear()
    
    def get_entities_for_export(self, filename: str) -> Dict[str, List[Any]]:
        """
        Возвращает словарь сущностей для экспорта, сгруппированных по слоям.
        
        Args:
            filename: Имя файла
            
        Returns:
            Словарь {layer_name: [entities]}
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
        
        return dict(self.msps[filename].groupby(dxfattrib="layer")) if filename in self.msps else {}
    
    def simple_read_dxf_file(self, file_name: str) -> Drawing:
        """
        Читает DXF файл и возвращает объект Drawing.
        
        Args:
            file_name: Путь к файлу
            
        Returns:
            ezdxf Drawing объект
        """
        doc = ezdxf.readfile(file_name)
        return doc
    
    def save_dxf_file(self, filename: str, output_path: str) -> bool:
        """
        Сохраняет DXF файл по указанному пути.

        Args:
            filename: Имя файла в обработчике
            output_path: Путь для сохранения файла

        Returns:
            True если сохранение успешно
        """
        try:
            if filename not in self.dxf:
                Logger.log_error(f"Файл {filename} не найден в загруженных файлах")
                return False

            doc = self.dxf[filename]
            doc.saveas(output_path)
            Logger.log_message(f"Файл {filename} успешно сохранен по пути: {output_path}")
            return True

        except Exception as e:
            Logger.log_error(f"Ошибка при сохранении файла {filename}: {str(e)}")
            return False
    
    def save_selected_entities(self, filename: str, output_file: str) -> bool:
        """
        Экспортирует выбранные сущности в новый DXF файл.

        Args:
            filename: Имя исходного DXF файла
            output_file: Путь выходного DXF файла
            
        Returns:
            True если экспорт успешен
        """
        if filename not in self.selected_entities:
            Logger.log_error(f"Нет выбранных сущностей для файла {filename}.")
            return False

        selected_entities = self.selected_entities[filename]
        if not selected_entities:
            Logger.log_error(f"Нет выбранных сущностей для экспорта из файла {filename}.")
            return False

        try:
            # Используем функцию write_block из модуля xref для создания нового документа
            new_doc = xref.write_block(selected_entities, origin=(0, 0, 0))

            layout_names = [name for name in self.dxf[filename].layout_names() if name != "Model"]
            try:
                for layout_name in layout_names:
                    xref.load_paperspace(
                        self.dxf[filename].paperspace(layout_name), 
                        new_doc, 
                        conflict_policy=ConflictPolicy.NUM_PREFIX
                    )
            except Exception as e:
                Logger.log_error(f"Ошибка при загрузке layout {layout_name}: {e}")
            
            new_doc.delete_layout('Layout1')

            # Сохраняем новый документ
            new_doc.saveas(output_file)
            Logger.log_message(f"Выбранные сущности успешно экспортированы в файл {output_file}.")
            return True

        except Exception as e:
            Logger.log_error(f"Ошибка при экспорте сущностей: {e}")
            return False
    
    def get_loaded_files(self) -> List[str]:
        """
        Возвращает список загруженных файлов.
        
        Returns:
            Список имён загруженных файлов
        """
        return list(self.dxf.keys())
    
    def get_layers(self, filename: str) -> List[str]:
        """
        Возвращает список слоёв в файле.
        
        Args:
            filename: Имя файла
            
        Returns:
            Список имён слоёв
        """
        if filename not in self.msps:
            return []
        
        layers = self.msps[filename].groupby(dxfattrib="layer")
        return list(layers.keys())
    
    def get_entities_count(self, filename: str) -> int:
        """
        Возвращает общее количество сущностей в файле.
        
        Args:
            filename: Имя файла
            
        Returns:
            Количество сущностей
        """
        return self.len_entities_file.get(filename, 0)
