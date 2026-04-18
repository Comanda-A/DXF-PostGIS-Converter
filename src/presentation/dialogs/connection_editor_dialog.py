from __future__ import annotations

import os
import sip
import inject

from qgis.PyQt.QtWidgets import QDialog, QTreeWidgetItem, QMessageBox, QMenu
from qgis.PyQt import uic

from ...application.dtos import ConnectionConfigDTO
from ...application.interfaces import ILocalization
from ...application.services import ConnectionConfigService
from ...application.database import DBSession
from ...presentation.services import DialogTranslator


FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), '.', 'resources', 'connection_editor_dialog.ui')
)


class ConnectionEditorDialog(QDialog, FORM_CLASS):

    @inject.autoparams('connection_service', 'session', 'localization')
    def __init__(
        self,
        parent,
        connection_service: ConnectionConfigService,
        session: DBSession,
        localization: ILocalization
    ):
        super().__init__(parent)
        self.setupUi(self)

        self._connection_service = connection_service
        self._session = session
        self._localization = localization
        self._selected_connection: ConnectionConfigDTO | None = None
        self._all_configs: list[ConnectionConfigDTO] = []

        self._connect_signals()
        self._update_language()
        self._refresh_connections_list()
        self.select_button.setEnabled(False)

    @property
    def selected_connection(self) -> ConnectionConfigDTO | None:
        return self._selected_connection

    def tr(self, key: str, *args) -> str:
        return self._localization.tr("CONNECTION_EDITOR_DIALOG", key, *args)

    def _connect_signals(self) -> None:
        self.treeWidget.customContextMenuRequested.connect(self._show_context_menu)
        self.treeWidget.itemExpanded.connect(self._on_item_expanded)
        self.treeWidget.itemSelectionChanged.connect(self._on_selection_changed)

        self.update_button.clicked.connect(self._refresh_connections_list)
        self.add_button.clicked.connect(self._on_add_button_click)
        self.select_button.clicked.connect(self._on_select_button_click)

    def _update_language(self) -> None:
        DialogTranslator().translate(self, "CONNECTION_EDITOR_DIALOG")

    def _refresh_connections_list(self) -> None:
        """Полная перезагрузка дерева."""
        self.treeWidget.clear()
        self._all_configs = self._connection_service.get_all_configs()

        for config in self._all_configs:
            item = QTreeWidgetItem([f"{config.name} ({config.db_type})"])
            item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            self.treeWidget.addTopLevelItem(item)

        self.select_button.setEnabled(False)

    def _reload_configs_only(self) -> None:
        """
        Обновить только кэш _all_configs — БЕЗ пересоздания дерева.
        Используется внутри _on_item_expanded, чтобы не инвалидировать item.
        """
        self._all_configs = self._connection_service.get_all_configs()

    def _get_connection_name_from_item(self, item: QTreeWidgetItem) -> str:
        text = item.text(0)  # "name (db_type)"
        return text.split(" (")[0] if " (" in text else text

    def _get_connection_by_name(self, name: str) -> ConnectionConfigDTO | None:
        for config in self._all_configs:
            if config.name == name:
                return config
        return None

    def _find_top_level_item(self, conn_name: str) -> QTreeWidgetItem | None:
        """
        Найти живой верхний элемент дерева по имени подключения.
        После любого exec_() ссылка на старый item может быть невалидна —
        ищем заново по имени.
        """
        for i in range(self.treeWidget.topLevelItemCount()):
            item = self.treeWidget.topLevelItem(i)
            if item and not sip.isdeleted(item):
                if self._get_connection_name_from_item(item) == conn_name:
                    return item
        return None

    def _has_credentials(self, config: ConnectionConfigDTO) -> bool:
        return (
            bool(config.username and config.username.strip())
            and bool(config.password and config.password.strip())
        )

    def _on_selection_changed(self) -> None:
        current = self.treeWidget.currentItem()
        enabled = (
            current is not None
            and not sip.isdeleted(current)
            and current.parent() is None
        )
        self.select_button.setEnabled(enabled)

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        """Раскрытие узла — загрузка схем и таблиц."""
        if item.childCount() > 0:
            return

        # Запоминаем имя ДО открытия любого диалога —
        # после exec_() item может быть удалён
        conn_name = self._get_connection_name_from_item(item)
        connection = self._get_connection_by_name(conn_name)
        if not connection:
            return

        if not self._has_credentials(connection):
            from ...presentation.dialogs import ConnectionDialog
            dialog = ConnectionDialog(self)
            dialog.set_connection_data(connection)

            accepted = dialog.exec_() == QDialog.Accepted

            # ★ После exec_() ConnectionDialog мог вызвать save_config.
            #   Обновляем только кэш — дерево НЕ трогаем.
            self._reload_configs_only()

            if not accepted:
                # Пользователь отменил — сворачиваем обратно.
                # item искать не нужно — просто находим его заново.
                fresh_item = self._find_top_level_item(conn_name)
                if fresh_item and not sip.isdeleted(fresh_item):
                    self.treeWidget.collapseItem(fresh_item)
                return

            # ★ Получаем свежую ссылку на item и свежий конфиг из кэша
            connection = self._get_connection_by_name(conn_name)
            item = self._find_top_level_item(conn_name)

            if not connection or not item or sip.isdeleted(item):
                return

        self._load_schemas(item, connection)

    def _load_schemas(
        self,
        parent_item: QTreeWidgetItem,
        config: ConnectionConfigDTO
    ) -> None:
        """Загрузка схем и таблиц для подключения."""
        if sip.isdeleted(parent_item):
            return

        self._session.connect(config)

        if not self._session.is_connected:
            self._add_error_child(parent_item, self.tr("schemas_load_failed"))
            QMessageBox.critical(
                self, self.tr("error_title"), self.tr("schemas_load_error")
            )
            return

        schemas_result = self._session.get_schemas()

        # ★ Проверяем после IO-операции
        if sip.isdeleted(parent_item):
            self._session.close()
            return

        if schemas_result.is_fail:
            self._add_error_child(parent_item, self.tr("schemas_load_failed"))
            QMessageBox.critical(
                self, self.tr("error_title"), self.tr("schemas_load_error")
            )
            self._session.close()
            return

        schemas: list[str] = schemas_result.value

        if not schemas:
            self._add_error_child(parent_item, self.tr("no_schemas_available"))
            self._session.close()
            return

        for schema_name in schemas:
            schema_item = QTreeWidgetItem([schema_name])
            parent_item.addChild(schema_item)

            tables_result = self._session.get_tables(schema_name)
            if tables_result.is_fail:
                self._add_error_child(schema_item, self.tr("tables_load_failed"))
                continue

            for table_name in tables_result.value:
                schema_item.addChild(QTreeWidgetItem([table_name]))

        self._session.close()

    def _add_error_child(self, parent: QTreeWidgetItem, text: str) -> None:
        if not sip.isdeleted(parent):
            parent.addChild(QTreeWidgetItem([text]))

    def _show_context_menu(self, position) -> None:
        item = self.treeWidget.itemAt(position)
        if not item or item.parent() is not None:
            return

        conn_name = self._get_connection_name_from_item(item)
        connection = self._get_connection_by_name(conn_name)
        if not connection:
            return

        menu = QMenu()
        edit_action = menu.addAction(self.tr("edit_action"))
        edit_action.triggered.connect(
            lambda: self._on_edit_connection(connection)
        )
        delete_action = menu.addAction(self.tr("delete_action"))
        delete_action.triggered.connect(
            lambda: self._on_delete_connection(connection)
        )
        menu.exec_(self.treeWidget.viewport().mapToGlobal(position))

    def _on_add_button_click(self) -> None:
        from ...presentation.dialogs import ConnectionDialog
        dialog = ConnectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self._refresh_connections_list()

    def _on_edit_connection(self, connection: ConnectionConfigDTO) -> None:
        from ...presentation.dialogs import ConnectionDialog
        dialog = ConnectionDialog(self)
        dialog.set_connection_data(connection)
        if dialog.exec_() == QDialog.Accepted:
            self._refresh_connections_list()

    def _on_delete_connection(self, connection: ConnectionConfigDTO) -> None:
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

    def _on_select_button_click(self) -> None:
        current_item = self.treeWidget.currentItem()

        if not current_item or current_item.parent() is not None:
            QMessageBox.information(
                self,
                self.tr("info_title"),
                self.tr("select_connection_prompt")
            )
            return

        conn_name = self._get_connection_name_from_item(current_item)
        connection = self._get_connection_by_name(conn_name)
        if not connection:
            return

        if not self._has_credentials(connection):
            from ...presentation.dialogs import ConnectionDialog
            dialog = ConnectionDialog(self)
            dialog.set_connection_data(connection)

            if dialog.exec_() == QDialog.Accepted:
                # Здесь _refresh_connections_list безопасен —
                # item нам больше не нужен
                self._refresh_connections_list()
                connection = self._get_connection_by_name(conn_name)
                if not connection:
                    return
            else:
                return

        self._selected_connection = connection
        self.accept()