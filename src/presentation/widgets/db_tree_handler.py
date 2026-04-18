from __future__ import annotations

import os
import sip
from pathlib import Path

from qgis.PyQt.QtWidgets import (
    QTreeWidgetItem, QPushButton, QWidget,
    QHBoxLayout, QHeaderView, QMessageBox
)
from qgis.PyQt.QtCore import Qt, QObject

from ...application.interfaces import ILocalization, ILogger
from .svg_preview_dialog import SvgPreviewDialog


class DbTreeWidgetHandler(QObject):
    """Обработчик дерева БД с кнопками превью, инфо и удалить."""

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

        self._on_preview_click = on_preview_click
        self._on_info_click = on_info_click
        self._on_delete_click = on_delete_click

        self._preview_dir = Path(__file__).resolve().parents[4] / "previews"

        self._tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._tree_widget.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)

    # ------------------------------------------------------------------ #
    #  Public                                                              #
    # ------------------------------------------------------------------ #

    def add_item(self, filename: str, has_preview: bool = False):
        """Добавляет элемент в дерево с кнопками действий."""
        item = QTreeWidgetItem([filename])
        item.setFlags(
            item.flags()
            | Qt.ItemIsUserCheckable
            | Qt.ItemIsSelectable
            | Qt.ItemIsEnabled
        )
        item.setCheckState(0, Qt.Unchecked)

        self._tree_widget.addTopLevelItem(item)
        self._add_action_buttons_to_item(filename)

    def clear(self):
        """Очищает дерево."""
        self._tree_widget.clear()

    def set_enabled(self, enabled: bool):
        """Включает/отключает дерево."""
        self._tree_widget.setEnabled(enabled)

    def get_checked_items(self) -> list[str]:
        """Возвращает список отмеченных элементов."""
        result = []
        for i in range(self._tree_widget.topLevelItemCount()):
            item = self._tree_widget.topLevelItem(i)
            if item and not sip.isdeleted(item):
                if item.checkState(0) == Qt.Checked:
                    result.append(item.text(0))
        return result

    def get_selected_items(self) -> list[str]:
        """Возвращает список выделенных элементов."""
        return [
            item.text(0)
            for item in self._tree_widget.selectedItems()
            if not sip.isdeleted(item)
        ]

    # ------------------------------------------------------------------ #
    #  Private                                                             #
    # ------------------------------------------------------------------ #

    def _find_item_by_filename(self, filename: str) -> QTreeWidgetItem | None:
        """
        Найти живой QTreeWidgetItem по имени файла.
        Вызывается в момент действия — не хранит ссылку заранее.
        """
        for i in range(self._tree_widget.topLevelItemCount()):
            item = self._tree_widget.topLevelItem(i)
            if item and not sip.isdeleted(item) and item.text(0) == filename:
                return item
        return None

    def _add_action_buttons_to_item(self, filename: str):
        """
        Добавляет кнопки к элементу.
        
        ★ item НЕ захватывается в лямбдах — ищем его динамически по filename.
          Это исключает RuntimeError при удалённом C++-объекте.
        ★ Лямбды явно игнорируют аргумент checked (bool) от сигнала clicked,
          чтобы исключить случайный двойной вызов.
        """
        # Находим только что добавленный item
        item = self._find_item_by_filename(filename)
        if not item:
            return

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Кнопка превью
        preview_button = QPushButton(
            self._localization.tr("DB_TREE_HANDLER", "preview_button")
        )
        preview_button.setFixedSize(80, 20)
        preview_button.setToolTip("Показать превью")
        # ★ checked=False — явно поглощаем аргумент сигнала clicked(bool)
        preview_button.clicked.connect(
            lambda checked=False: self._on_preview_button_click(filename)
        )
        layout.addWidget(preview_button)

        # Кнопка инфо
        info_button = QPushButton(
            self._localization.tr("DB_TREE_HANDLER", "info_button")
        )
        info_button.setFixedSize(80, 20)
        info_button.clicked.connect(
            lambda checked=False: self._on_info_button_click(filename)
        )
        layout.addWidget(info_button)

        # Кнопка удалить
        delete_button = QPushButton(
            self._localization.tr("DB_TREE_HANDLER", "delete_button")
        )
        delete_button.setFixedSize(80, 20)
        delete_button.clicked.connect(
            lambda checked=False: self._on_delete_button_click(filename)
        )
        layout.addWidget(delete_button)

        layout.setAlignment(Qt.AlignRight)
        widget.setLayout(widget.layout() or layout)

        self._tree_widget.setItemWidget(item, 1, widget)

    def _on_preview_button_click(self, filename: str):
        """Обработчик кнопки превью."""
        preview_path = self._preview_dir / f"{Path(filename).stem}.svg"

        if os.path.exists(str(preview_path)):
            dialog = SvgPreviewDialog(
                str(preview_path), self._parent or self._tree_widget
            )
            dialog.exec_()
        else:
            QMessageBox.information(
                self._parent or self._tree_widget,
                "Информация",
                f"Превью для '{filename}' не найдено"
            )

        if self._on_preview_click:
            self._on_preview_click(filename)

    def _on_info_button_click(self, filename: str):
        """Обработчик кнопки инфо."""
        if self._on_info_click:
            self._on_info_click(filename)

    def _on_delete_button_click(self, filename: str):
        """Обработчик кнопки удалить."""
        # Убираем диалог отсюда
        if self._on_delete_click:
            self._on_delete_click(filename)