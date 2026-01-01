# -*- coding: utf-8 -*-
"""
DxfDocument - чистая работа с DXF документами.

Не зависит от UI! Работает только с ezdxf.
"""

import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

import ezdxf
from ezdxf import select
from ezdxf.document import Drawing
from ezdxf.layouts.layout import Modelspace
from ezdxf.entities import DXFEntity
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing import layout, svg

from ...logger.logger import Logger


class SelectionMode(Enum):
    """Режим выбора сущностей."""
    INSIDE = "inside"
    OUTSIDE = "outside"
    INTERSECT = "intersect"


class ShapeType(Enum):
    """Тип фигуры для выделения."""
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    POLYGON = "polygon"


@dataclass
class SelectionShape:
    """Параметры фигуры для выделения."""
    shape_type: ShapeType
    # Для прямоугольника: (x_min, x_max, y_min, y_max)
    # Для круга: (center_x, center_y, radius)
    # Для полигона: [(x1, y1), (x2, y2), ...]
    params: tuple


class DxfDocument:
    """
    Чистая работа с DXF документом.
    
    Не зависит от UI! Инкапсулирует работу с ezdxf.
    """
    
    def __init__(self, file_path: Optional[str] = None):
        """
        Args:
            file_path: Путь к DXF файлу (опционально)
        """
        self._doc: Optional[Drawing] = None
        self._msp: Optional[Modelspace] = None
        self._file_path: Optional[str] = None
        self._filename: Optional[str] = None
        
        if file_path:
            self.load(file_path)
    
    @property
    def is_loaded(self) -> bool:
        """Загружен ли документ."""
        return self._doc is not None
    
    @property
    def filename(self) -> Optional[str]:
        """Имя файла."""
        return self._filename
    
    @property
    def file_path(self) -> Optional[str]:
        """Путь к файлу."""
        return self._file_path
    
    @property
    def modelspace(self) -> Optional[Modelspace]:
        """ModelSpace документа."""
        return self._msp
    
    @property
    def document(self) -> Optional[Drawing]:
        """Оригинальный документ ezdxf."""
        return self._doc
    
    def load(self, file_path: str) -> bool:
        """
        Загрузить DXF файл.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            True если успешно
        """
        try:
            self._doc = ezdxf.readfile(file_path)
            self._doc.audit()
            self._msp = self._doc.modelspace()
            self._file_path = file_path
            self._filename = os.path.basename(file_path)
            
            Logger.log_message(f"DXF файл '{self._filename}' загружен")
            return True
            
        except IOError as e:
            Logger.log_error(f"Файл не найден: {file_path}")
            self._reset()
            return False
        except ezdxf.DXFStructureError as e:
            Logger.log_error(f"Неверный формат DXF: {file_path}")
            self._reset()
            return False
        except Exception as e:
            Logger.log_error(f"Ошибка загрузки DXF: {str(e)}")
            self._reset()
            return False
    
    def get_layers(self) -> Dict[str, List[DXFEntity]]:
        """
        Получить все сущности, сгруппированные по слоям.
        
        Returns:
            Словарь {layer_name: [entities]}
        """
        if not self.is_loaded:
            return {}
        
        return dict(self._msp.groupby(dxfattrib="layer"))
    
    def get_layer_names(self) -> List[str]:
        """Получить список имён слоёв."""
        return list(self.get_layers().keys())
    
    def get_entities_by_layer(self, layer_name: str) -> List[DXFEntity]:
        """
        Получить сущности конкретного слоя.
        
        Args:
            layer_name: Имя слоя
            
        Returns:
            Список сущностей
        """
        layers = self.get_layers()
        return list(layers.get(layer_name, []))
    
    def get_all_entities(self) -> List[DXFEntity]:
        """Получить все сущности."""
        if not self.is_loaded:
            return []
        return list(self._msp)
    
    def get_entity_count(self) -> int:
        """Количество сущностей в документе."""
        layers = self.get_layers()
        return sum(len(entities) for entities in layers.values())
    
    def select_in_area(
        self, 
        shape: SelectionShape, 
        mode: SelectionMode
    ) -> List[DXFEntity]:
        """
        Выбрать сущности в области.
        
        Args:
            shape: Параметры фигуры выделения
            mode: Режим выделения
            
        Returns:
            Список выбранных сущностей
        """
        if not self.is_loaded:
            return []
        
        # Создаём объект фигуры
        shape_obj = self._create_shape(shape)
        if shape_obj is None:
            return []
        
        # Получаем функцию выбора
        selection_func = self._get_selection_function(mode)
        
        return list(selection_func(shape_obj, self._msp))
    
    def save_svg_preview(self, output_dir: str) -> Optional[str]:
        """
        Сохранить SVG превью документа.
        
        Args:
            output_dir: Директория для сохранения
            
        Returns:
            Путь к SVG файлу или None
        """
        if not self.is_loaded:
            return None
        
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            preview_filename = f"{os.path.splitext(self._filename)[0]}.svg"
            preview_path = os.path.join(output_dir, preview_filename)
            
            backend = svg.SVGBackend()
            Frontend(RenderContext(self._doc), backend).draw_layout(self._msp)
            
            with open(preview_path, "wt") as fp:
                fp.write(backend.get_string(layout.Page(0, 0)))
            
            Logger.log_message(f"SVG превью сохранено: {preview_path}")
            return preview_path
            
        except Exception as e:
            Logger.log_error(f"Ошибка сохранения SVG: {str(e)}")
            return None
    
    # ========== Приватные методы ==========
    
    def _reset(self) -> None:
        """Сбросить состояние."""
        self._doc = None
        self._msp = None
        self._file_path = None
        self._filename = None
    
    def _create_shape(self, shape: SelectionShape) -> Optional[Any]:
        """Создать объект фигуры ezdxf."""
        try:
            if shape.shape_type == ShapeType.RECTANGLE:
                x_min, x_max, y_min, y_max = shape.params
                return select.Window((x_min, y_min), (x_max, y_max))
            
            elif shape.shape_type == ShapeType.CIRCLE:
                center_x, center_y, radius = shape.params
                return select.Circle((center_x, center_y), radius)
            
            elif shape.shape_type == ShapeType.POLYGON:
                points = shape.params
                return select.Polygon(points)
            
            return None
            
        except Exception as e:
            Logger.log_error(f"Ошибка создания фигуры: {str(e)}")
            return None
    
    def _get_selection_function(self, mode: SelectionMode):
        """Получить функцию выбора по режиму."""
        functions = {
            SelectionMode.INSIDE: select.bbox_inside,
            SelectionMode.OUTSIDE: select.bbox_outside,
            SelectionMode.INTERSECT: select.bbox_overlap,
        }
        return functions.get(mode, select.bbox_overlap)
