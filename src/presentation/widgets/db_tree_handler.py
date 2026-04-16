from __future__ import annotations

import os
from pathlib import Path

from qgis.PyQt.QtWidgets import QTreeWidgetItem, QPushButton, QWidget, QHBoxLayout, QHeaderView, QMessageBox
from qgis.PyQt.QtCore import Qt, QObject

from ...application.interfaces import ILocalization, ILogger
from ...presentation.services.progress_task_runner import ProgressTaskRunner
from .svg_preview_dialog import SvgPreviewDialog


class DbTreeWidgetHandler(QObject):
    """Обработчик дерева БД с кнопками превью, инфо и удалить"""

    def __init__(
        self,
        tree_widget,
        localization: ILocalization,
        logger: ILogger,
        on_preview_click=None,
        on_info_click=None,
        on_delete_click=None,
        parent=None
    ):
        super().__init__()
        
        self._tree_widget = tree_widget
        self._localization = localization
        self._logger = logger
        self._parent = parent
        
        # Callbacks для обработки действий
        self._on_preview_click = on_preview_click
        self._on_info_click = on_info_click
        self._on_delete_click = on_delete_click
        
        # Инициализация пути к папке с превью
        self._preview_dir = Path(__file__).resolve().parents[4] / "previews"
        
        # Настройка заголовков
        self._tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._tree_widget.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)

    def add_item(self, filename: str, has_preview: bool = False):
        """Добавляет элемент в дерево с кнопками действий"""
        item = QTreeWidgetItem([filename])
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        item.setCheckState(0, Qt.Unchecked)
        
        self._tree_widget.addTopLevelItem(item)
        self._add_action_buttons_to_item(item, filename)

    def _add_action_buttons_to_item(self, item: QTreeWidgetItem, filename: str):
        """Добавляет кнопки превью, инфо и удалить к элементу"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Кнопка превью
        preview_button = QPushButton(self._localization.tr("DB_TREE_HANDLER", "preview_button"))
        preview_button.setFixedSize(80, 20)
        preview_button.setEnabled(True)
        preview_button.setToolTip("Показать превью")
        preview_button.clicked.connect(lambda: self._on_preview_button_click(filename, item))
        layout.addWidget(preview_button)
        
        # Кнопка инфо
        info_button = QPushButton(self._localization.tr("DB_TREE_HANDLER", "info_button"))
        info_button.setFixedSize(80, 20)
        info_button.clicked.connect(lambda: self._on_info_button_click(filename))
        layout.addWidget(info_button)
        
        # Кнопка удалить
        delete_button = QPushButton(self._localization.tr("DB_TREE_HANDLER", "delete_button"))
        delete_button.setFixedSize(80, 20)
        delete_button.clicked.connect(lambda: self._on_delete_button_click(item, filename))
        layout.addWidget(delete_button)
        
        layout.setAlignment(Qt.AlignRight)
        widget.setLayout(layout)

        self._tree_widget.setItemWidget(item, 1, widget)

    def _on_preview_button_click(self, filename: str, item: QTreeWidgetItem):
        """Обработчик нажатия кнопки превью"""
        preview_path = self._preview_dir / f"{Path(filename).stem}.svg"
        
        # Если превью существует - показываем его
        if os.path.exists(str(preview_path)):
            dialog = SvgPreviewDialog(str(preview_path), self._parent or self._tree_widget)
            dialog.exec_()
        else:
            QMessageBox.information(self._parent or self._tree_widget, "Информация", 
                f"Превью для '{filename}' не найдено")
        
        # Вызываем callback если он установлен
        if self._on_preview_click:
            self._on_preview_click(filename)

    def _on_info_button_click(self, filename: str):
        """Обработчик нажатия кнопки инфо"""
        # Вызываем callback
        if self._on_info_click:
            self._on_info_click(filename)

    def _on_delete_button_click(self, item: QTreeWidgetItem, filename: str):
        """Обработчик нажатия кнопки удалить"""
        # Запрашиваем подтверждение
        reply = QMessageBox.question(
            self._parent or self._tree_widget,
            "Подтверждение",
            f"Вы уверены что хотите удалить '{filename}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Вызываем callback
            if self._on_delete_click:
                self._on_delete_click(filename)
            
            # Удаляем элемент из дерева
            index = self._tree_widget.indexOfTopLevelItem(item)
            if index >= 0:
                self._tree_widget.takeTopLevelItem(index)

    def clear(self):
        """Очищает дерево"""
        self._tree_widget.clear()

    def set_enabled(self, enabled: bool):
        """Включает/отключает дерево"""
        self._tree_widget.setEnabled(enabled)

    def get_checked_items(self) -> list[str]:
        """Возвращает список выбранных элементов"""
        checked_items = []
        for i in range(self._tree_widget.topLevelItemCount()):
            item = self._tree_widget.topLevelItem(i)
            if item.checkState(0) == Qt.Checked:
                checked_items.append(item.text(0))
        return checked_items

    def get_selected_items(self) -> list[str]:
        """Возвращает список выделенных элементов"""
        selected_items = []
        for item in self._tree_widget.selectedItems():
            selected_items.append(item.text(0))
        return selected_items
