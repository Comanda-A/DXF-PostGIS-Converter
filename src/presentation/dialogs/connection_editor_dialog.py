from __future__ import annotations

import os
import inject

from qgis.PyQt.QtWidgets import QDialog, QTreeWidgetItem, QMessageBox, QMenu
from qgis.PyQt import uic

from ...application.dtos import ConnectionConfigDTO
from ...application.interfaces import ILocalization
from ...application.services import ConnectionConfigService
from ...application.database import DBSession
from ...presentation.services import DialogTranslator


# Load UI file from resources
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), '.', 'resources', 'connection_editor_dialog.ui'))

class ConnectionEditorDialog(QDialog, FORM_CLASS):
    
    @inject.autoparams('connection_service', 'session', 'localization')
    def __init__(
        self,
        parent,
        connection_service: ConnectionConfigService,
        session: DBSession,
        localization: ILocalization
    ):
        """Constructor."""
        super().__init__(parent)
        self.setupUi(self)

        self._connection_service = connection_service
        self._session = session
        self._localization = localization

        self._current_configs: dict[int, ConnectionConfigDTO] = {}
        self._selected_connection: ConnectionConfigDTO | None = None

        self._connect_signals()
        self._update_language()
        self._refresh_connections_list()
        
        # Изначально кнопка выбора неактивна
        self.select_button.setEnabled(False)
    
    @property
    def selected_connection(self):
        return self._selected_connection

    def tr(self, key: str, *args) -> str:
        translated = self._localization.tr("CONNECTION_EDITOR_DIALOG", key, *args)
        return translated
    
    def _connect_signals(self):
        """Подключение сигналов."""
        self.treeWidget.customContextMenuRequested.connect(self._show_context_menu)
        self.treeWidget.itemExpanded.connect(self._on_item_expanded)
        self.treeWidget.itemSelectionChanged.connect(self._on_selection_changed)

        self.update_button.clicked.connect(self._refresh_connections_list)
        self.add_button.clicked.connect(self._on_add_button_click)
        self.select_button.clicked.connect(self._on_select_button_click)
        
    def _update_language(self):
        """Обновление текстов UI."""
        DialogTranslator().translate(self, "CONNECTION_EDITOR_DIALOG")
    
    def _refresh_connections_list(self):
        """Обновление списка подключений."""
        self.treeWidget.clear()
        self._current_configs.clear()
        
        try:
            configs = self._connection_service.get_all_configs()
            
            for config in configs:
                item = QTreeWidgetItem([f"{config.name} ({config.db_type})"])
                item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                self.treeWidget.addTopLevelItem(item)
                
                # Сохраняем данные подключения
                self._current_configs[id(item)] = config
                
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("error_title"),
                self.tr("load_connections_error")
            )
        
        # После обновления списка кнопка выбора неактивна
        self.select_button.setEnabled(False)
    
    def _on_selection_changed(self):
        """Обработка изменения выделения в дереве."""
        current_item = self.treeWidget.currentItem()
        
        if current_item:
            # Проверяем, является ли выбранный элемент подключением
            # Для этого ищем родительский элемент - если его нет, значит это топ-уровень (подключение)
            is_connection = current_item.parent() is None and id(current_item) in self._current_configs
            
            # Активируем кнопку только если это подключение
            self.select_button.setEnabled(is_connection)
        else:
            self.select_button.setEnabled(False)
    
    def _on_item_expanded(self, item):
        """Обработка раскрытия элемента дерева."""
        # Получаем подключение по ID элемента
        connection = self._current_configs.get(id(item))
        if not connection:
            return
        
        # Проверяем, есть ли уже загруженные данные
        if item.childCount() == 0:
            self._load_schemas(item, connection)
    
    def _load_schemas(self, parent_item: QTreeWidgetItem, config: ConnectionConfigDTO):
        """Загрузка схем для подключения."""
        schemas: list[str] | None = None
        self._session.connect(config)
        if self._session.is_connected:
            schemas_result = self._session.get_schemas()
            if schemas_result.is_success:
                schemas = schemas_result.value

        if schemas is None:
            empty_item = QTreeWidgetItem([self.tr("schemas_load_failed")])
            parent_item.addChild(empty_item)
            QMessageBox.critical(
                self,
                self.tr("error_title"),
                self.tr("schemas_load_error")
            )
        elif not schemas:
            empty_item = QTreeWidgetItem([self.tr("no_schemas_available")])
            parent_item.addChild(empty_item)
        else:
            for schema_name in schemas:
                schema_item = QTreeWidgetItem([f"{schema_name}"])
                parent_item.addChild(schema_item)

                tables_result = self._session.get_tables(schema_name)
                if tables_result.is_fail:
                    empty_item = QTreeWidgetItem([self.tr("tables_load_failed")])
                    schema_item.addChild(empty_item)
                    continue

                for table_name in tables_result.value:
                    table_item = QTreeWidgetItem([table_name])
                    schema_item.addChild(table_item)
        
        self._session.close()
    
    def _show_context_menu(self, position):
        """Показ контекстного меню."""
        item = self.treeWidget.itemAt(position)
        if not item:
            return
        
        # Проверяем, является ли элемент подключением
        connection = self._current_configs.get(id(item))
        if not connection:
            return
        
        menu = QMenu()
        
        edit_action = menu.addAction(self.tr("edit_action"))
        edit_action.triggered.connect(lambda: self._on_edit_connection(connection))
        
        delete_action = menu.addAction(self.tr("delete_action"))
        delete_action.triggered.connect(lambda: self._on_delete_connection(connection))
        
        menu.exec_(self.treeWidget.viewport().mapToGlobal(position))
    
    def _on_edit_connection(self, connection: ConnectionConfigDTO):
        """Обработка редактирования подключения."""
        from ...presentation.dialogs import ConnectionDialog
        dialog = ConnectionDialog(self)
        dialog.set_connection_data(connection)
        if dialog.exec_() == QDialog.Accepted:
            self._refresh_connections_list()
    
    def _on_delete_connection(self, connection: ConnectionConfigDTO):
        """Обработка удаления подключения."""
        reply = QMessageBox.question(
            self,
            self.tr("delete_confirmation_title"),
            self.tr("delete_confirmation_message", connection.name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            result = self._connection_service.delete_config(connection.name)
            if result.is_success:
                self._refresh_connections_list()
            else:
                QMessageBox.warning(
                    self,
                    self.tr("error_title"),
                    self.tr("delete_error", connection.name)
                )

    def _on_add_button_click(self):
        """Обработка добавления нового подключения."""
        from ...presentation.dialogs import ConnectionDialog
        dialog = ConnectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self._refresh_connections_list()
    
    def _on_select_button_click(self):
        """Обработка выбора подключения."""
        current_item = self.treeWidget.currentItem()
        if current_item:
            connection = self._current_configs.get(id(current_item))
            if connection:
                # Сохраняем выбранное подключение и закрываем диалог
                self._selected_connection = connection
                self.accept()
                return
            
        QMessageBox.information(
            self,
            self.tr("info_title"),
            self.tr("select_connection_prompt")
        )