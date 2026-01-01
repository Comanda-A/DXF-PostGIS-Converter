# -*- coding: utf-8 -*-
"""
EntitySelector - управление выделением сущностей.

Чистая логика без UI. Отслеживает выбранные сущности для каждого документа.
"""

from typing import Dict, List, Optional, Set
from ezdxf.entities import DXFEntity

from .dxf_document import DxfDocument, SelectionShape, SelectionMode
from ...logger.logger import Logger


class EntitySelector:
    """
    Управление выделением сущностей.
    
    Чистая логика без UI! Хранит состояние выделения для каждого файла.
    """
    
    def __init__(self):
        # {filename: [entities]}
        self._selected_entities: Dict[str, List[DXFEntity]] = {}
        # {filename: DxfDocument}
        self._documents: Dict[str, DxfDocument] = {}
    
    def register_document(self, document: DxfDocument) -> None:
        """
        Зарегистрировать документ для отслеживания выделения.
        
        Args:
            document: DXF документ
        """
        if document.filename:
            self._documents[document.filename] = document
            # Изначально выбираем все сущности
            self._selected_entities[document.filename] = document.get_all_entities()
            Logger.log_message(
                f"Документ '{document.filename}' зарегистрирован, "
                f"выбрано {len(self._selected_entities[document.filename])} сущностей"
            )
    
    def unregister_document(self, filename: str) -> None:
        """Отменить регистрацию документа."""
        self._documents.pop(filename, None)
        self._selected_entities.pop(filename, None)
    
    def select_by_area(
        self, 
        filename: str, 
        shape: SelectionShape, 
        mode: SelectionMode
    ) -> List[DXFEntity]:
        """
        Выбрать сущности в области.
        
        Args:
            filename: Имя файла
            shape: Параметры фигуры выделения
            mode: Режим выделения
            
        Returns:
            Список выбранных сущностей
        """
        document = self._documents.get(filename)
        if not document:
            Logger.log_warning(f"Документ '{filename}' не зарегистрирован")
            return []
        
        entities = document.select_in_area(shape, mode)
        self._selected_entities[filename] = entities
        
        Logger.log_message(
            f"Выбрано {len(entities)} сущностей в '{filename}'"
        )
        return entities
    
    def select_by_layers(
        self, 
        filename: str, 
        layer_names: List[str]
    ) -> List[DXFEntity]:
        """
        Выбрать сущности указанных слоёв.
        
        Args:
            filename: Имя файла
            layer_names: Список имён слоёв
            
        Returns:
            Список выбранных сущностей
        """
        document = self._documents.get(filename)
        if not document:
            return []
        
        entities = []
        for layer_name in layer_names:
            entities.extend(document.get_entities_by_layer(layer_name))
        
        self._selected_entities[filename] = entities
        Logger.log_message(
            f"Выбрано {len(entities)} сущностей из слоёв {layer_names}"
        )
        return entities
    
    def select_entities(
        self, 
        filename: str, 
        entities: List[DXFEntity]
    ) -> None:
        """
        Установить выбранные сущности напрямую.
        
        Args:
            filename: Имя файла
            entities: Список сущностей
        """
        self._selected_entities[filename] = entities
        Logger.log_message(
            f"Установлено {len(entities)} выбранных сущностей для '{filename}'"
        )
    
    def select_all(self, filename: str) -> List[DXFEntity]:
        """
        Выбрать все сущности документа.
        
        Args:
            filename: Имя файла
            
        Returns:
            Список всех сущностей
        """
        document = self._documents.get(filename)
        if not document:
            return []
        
        entities = document.get_all_entities()
        self._selected_entities[filename] = entities
        return entities
    
    def clear_selection(self, filename: Optional[str] = None) -> None:
        """
        Очистить выделение.
        
        Args:
            filename: Имя файла. Если None, очищается всё.
        """
        if filename:
            self._selected_entities[filename] = []
        else:
            for key in self._selected_entities:
                self._selected_entities[key] = []
    
    def get_selection(self, filename: str) -> List[DXFEntity]:
        """
        Получить выбранные сущности.
        
        Args:
            filename: Имя файла
            
        Returns:
            Список выбранных сущностей
        """
        return self._selected_entities.get(filename, [])
    
    def get_selection_count(self, filename: str) -> int:
        """Получить количество выбранных сущностей."""
        return len(self.get_selection(filename))
    
    def get_total_count(self, filename: str) -> int:
        """Получить общее количество сущностей в документе."""
        document = self._documents.get(filename)
        return document.get_entity_count() if document else 0
    
    def has_partial_selection(self, filename: str) -> bool:
        """Проверить, выбрана ли часть (не все) сущности."""
        selected = self.get_selection_count(filename)
        total = self.get_total_count(filename)
        return 0 < selected < total
    
    def get_selection_by_layers(self, filename: str) -> Dict[str, List[DXFEntity]]:
        """
        Получить выбранные сущности, сгруппированные по слоям.
        
        Args:
            filename: Имя файла
            
        Returns:
            Словарь {layer_name: [entities]}
        """
        entities = self.get_selection(filename)
        
        result: Dict[str, List[DXFEntity]] = {}
        for entity in entities:
            layer = entity.dxf.layer
            if layer not in result:
                result[layer] = []
            result[layer].append(entity)
        
        return result
    
    def get_registered_files(self) -> List[str]:
        """Получить список зарегистрированных файлов."""
        return list(self._documents.keys())
    
    def get_document(self, filename: str) -> Optional[DxfDocument]:
        """Получить документ по имени файла."""
        return self._documents.get(filename)
