
from qgis.PyQt.QtWidgets import QTreeWidget, QTreeWidgetItem
from qgis.PyQt.QtCore import QObject

from ...application.dtos import DXFBaseDTO, DXFDocumentDTO, DXFLayerDTO

class ViewerDxfTreeHandler(QObject):

    def __init__(
            self,
            tree_widget: QTreeWidget
    ):
        super().__init__()

        self._tree_widget = tree_widget
        self._only_selected = True

        self._item_to_dto: list[tuple[QTreeWidgetItem, DXFBaseDTO]] = []
        self._tree_widget.itemExpanded.connect(self._on_item_expanded)
    
    def _get_dto_for_item(self, item: QTreeWidgetItem) -> DXFBaseDTO | None:
        """Находит селектор для элемента дерева"""
        for stored_item, stored_selector in self._item_to_dto:
            if stored_item is item:  # Сравнение по идентичности объекта
                return stored_selector
        return None
    
    def rebuild_tree(self, documents: list[DXFDocumentDTO], only_selected = False):
        """Создаёт только верхний уровень (файлы)"""

        self._only_selected = only_selected
        self._tree_widget.clear()
        self._item_to_dto.clear()
        
        for doc in documents:
            
            if self._only_selected and not doc.selected:
                continue
            
            doc_item = QTreeWidgetItem([doc.filename])
            doc_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            
            # Сохраняем связь item -> selector
            self._item_to_dto.append((doc_item, doc))
            
            self._tree_widget.addTopLevelItem(doc_item)
    
    def _on_item_expanded(self, item: QTreeWidgetItem):
        """Заполняет дочерние элементы при раскрытии"""

        # Проверяем, нужно ли заполнять
        if item.childCount() > 0:
            return
            
        dto = self._get_dto_for_item(item)
        
        if dto is None:
            return
        
        if isinstance(dto, DXFDocumentDTO):
            # Заполняем слои для файла
            for layer in dto.layers:
                if self._only_selected and not layer.selected:
                    continue
                layer_item = QTreeWidgetItem([layer.name])
                layer_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                item.addChild(layer_item)
                
                # Сохраняем связь
                self._item_to_dto.append((layer_item, layer))
        
        elif isinstance(dto, DXFLayerDTO):
            # Заполняем сущности для слоя
            for entity in dto.entities:
                if self._only_selected and not entity.selected:
                    continue   
                entity_item = QTreeWidgetItem([entity.name])
                item.addChild(entity_item)
                
                # Сохраняем связь
                self._item_to_dto.append((entity_item, entity))