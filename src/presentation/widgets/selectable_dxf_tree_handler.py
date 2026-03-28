import inject

from qgis.PyQt.QtWidgets import QTreeWidgetItem, QPushButton, QWidget, QHBoxLayout, QHeaderView
from qgis.PyQt.QtCore import Qt, QSignalBlocker, QObject

from ...application.dtos import DXFBaseDTO, DXFDocumentDTO, DXFLayerDTO
from ...application.use_cases import CloseDocumentUseCase, SelectEntityUseCase
from ...application.services import ActiveDocumentService
from ...application.interfaces import ILocalization, ILogger

class SelectableDxfTreeHandler(QObject):
    """Обработчик дерева DXF с поддержкой ленивой загрузки"""

    @inject.autoparams(
        'close_doc_use_case',
        'select_entity_use_case',
        'active_doc_service',
        'localization',
        'logger'
    )
    def __init__(
        self,
        tree_widget,
        close_doc_use_case: CloseDocumentUseCase,
        select_entity_use_case: SelectEntityUseCase,
        active_doc_service: ActiveDocumentService,
        localization: ILocalization,
        logger: ILogger
    ):
        super().__init__()
        
        self._tree_widget = tree_widget
        self._close_doc_use_case = close_doc_use_case
        self._select_entity_use_case = select_entity_use_case
        self._active_doc_service = active_doc_service
        self._localization = localization
        self._logger = logger

        self._item_to_dto: list[tuple[QTreeWidgetItem, DXFBaseDTO]] = [] 
        
        # Сигналы дерева
        self._tree_widget.itemChanged.connect(self._on_item_check_changed)
        
        # Настройка заголовков
        self._tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._tree_widget.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)

    def _get_dto_for_item(self, item: QTreeWidgetItem) -> DXFBaseDTO | None:
        """Находит селектор для элемента дерева"""
        for stored_item, stored_dto in self._item_to_dto:
            if stored_item is item:
                return stored_dto
        return None

    def _add_remove_button_to_item(self, item: QTreeWidgetItem):
        """Добавляет кнопку удаления к элементу файла"""
        remove_button = QPushButton(self._localization.tr("TREE_WIDGET_HANDLER", "remove_button"))
        remove_button.setFixedSize(80, 20)
        remove_button.clicked.connect(lambda: self._on_remove_button_click(item))

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.addWidget(remove_button)
        layout.setAlignment(Qt.AlignRight)
        layout.setContentsMargins(0, 0, 0, 0)
        widget.setLayout(layout)

        self._tree_widget.setItemWidget(item, 1, widget)

    def _on_remove_button_click(self, item: QTreeWidgetItem):
        """Обработчик нажатия кнопки удаления"""
        dto = self._get_dto_for_item(item)
        if dto is None:
            return
        result = self._close_doc_use_case.execute(dto.id)
        if result.is_fail:
            self._logger.error(f"Failed to close document: {result.error}")

    def _on_item_check_changed(self, item: QTreeWidgetItem, column: int):
        """Обработчик изменения состояния элемента дерева (чекбокса)"""
        if not (item.flags() & Qt.ItemIsUserCheckable):
            return
        
        for i, item_pair in enumerate(self._item_to_dto):
            stored_item, stored_dto = item_pair
            if stored_item is item:
                with QSignalBlocker(self._tree_widget):
                    new_state = item.checkState(0)
                    is_selected = new_state == Qt.Checked
                    result = self._select_entity_use_case.execute_single(stored_dto.id, is_selected)
                    if result.is_fail:
                        self._logger.error(f'Select entity error {result.error}')
                    return

    def update_tree(self):
        """Обновляет состояние элементов дерева"""
        self._tree_widget.setUpdatesEnabled(False)
        with QSignalBlocker(self._tree_widget):
            try:
                # Обновляем только существующие элементы
                updated_pairs = []
                for item, dto in self._item_to_dto:
                    try:
                        # Проверяем что элемент валиден
                        _ = item.text(0)
                        
                        refreshed_dto = self._active_doc_service.get_by_id(dto.id)

                        # Обновляем состояние чекбокса
                        item.setCheckState(0, Qt.Checked if refreshed_dto.selected else Qt.Unchecked)
                        
                        # Обновляем текст для файлов и слоев
                        if isinstance(refreshed_dto, DXFDocumentDTO):
                            item.setText(0, self._localization.tr("TREE_WIDGET_HANDLER", "file_text",
                                refreshed_dto.filename,
                                sum(1 for layer in refreshed_dto.layers if layer.selected),
                                len(refreshed_dto.layers),
                                sum(sum(1 for e in layer.entities if e.selected) for layer in refreshed_dto.layers),
                                sum(len(layer.entities) for layer in refreshed_dto.layers)
                            ))
                        elif isinstance(refreshed_dto, DXFLayerDTO):
                            item.setText(0, self._localization.tr("TREE_WIDGET_HANDLER", "layer_text",
                                refreshed_dto.name,
                                sum(1 for e in refreshed_dto.entities if e.selected), 
                                len(refreshed_dto.entities)
                            ))
                        
                        updated_pairs.append((item, refreshed_dto))
                            
                    except (RuntimeError, AttributeError):
                        # Элемент был удален
                        continue
                
                self._item_to_dto = updated_pairs
                
            finally:
                self._tree_widget.setUpdatesEnabled(True)

    def rebuild_tree(self, documents: list[DXFDocumentDTO]):
        """Полностью перестраивает дерево"""
        self._tree_widget.setUpdatesEnabled(False)
        self._tree_widget.clear()
        self._item_to_dto.clear()
        
        try:
            for doc in documents:

                file_item = QTreeWidgetItem([
                    self._localization.tr("TREE_WIDGET_HANDLER", "file_text",
                        doc.filename,
                        sum(1 for layer in doc.layers if layer.selected),
                        len(doc.layers),
                        sum(sum(1 for e in layer.entities if e.selected) for layer in doc.layers),
                        sum(len(layer.entities) for layer in doc.layers)
                    )
                ])
                
                file_item.setCheckState(0, Qt.Checked if doc.selected else Qt.Unchecked)
                file_item.setFlags(file_item.flags() | Qt.ItemIsUserCheckable)
                file_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                
                self._tree_widget.addTopLevelItem(file_item)
                self._item_to_dto.append((file_item, doc))
                self._add_remove_button_to_item(file_item)

                for layer in doc.layers:
                    layer_item = QTreeWidgetItem([
                        self._localization.tr("TREE_WIDGET_HANDLER", "layer_text",
                            layer.name,
                            sum(1 for e in layer.entities if e.selected), 
                            len(layer.entities)
                        )
                    ])
                    
                    layer_item.setCheckState(0, Qt.Checked if layer.selected else Qt.Unchecked)
                    layer_item.setFlags(layer_item.flags() | Qt.ItemIsUserCheckable)
                    layer_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                    file_item.addChild(layer_item)
                    self._item_to_dto.append((layer_item, layer))

                    for entity in layer.entities:
                        entity_item = QTreeWidgetItem([entity.name])
                        entity_item.setCheckState(0, Qt.Checked if entity.selected else Qt.Unchecked)
                        entity_item.setFlags(entity_item.flags() | Qt.ItemIsUserCheckable)
                        layer_item.addChild(entity_item)
                        self._item_to_dto.append((entity_item, entity))

        finally:
            self._tree_widget.setUpdatesEnabled(True)