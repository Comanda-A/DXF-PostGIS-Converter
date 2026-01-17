# -*- coding: utf-8 -*-
"""
Main Dialog - главный диалог.

Использует DependencyContainer для инъекции зависимостей.
Делегирует бизнес-логику сервисам.
"""

import os
import tempfile
from typing import Optional, Dict, Any

from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import (
    QMessageBox, QTreeWidgetItem, QPushButton, QWidget, 
    QHBoxLayout, QHeaderView, QFileDialog, QProgressDialog
)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QTimer, QEvent
from qgis.core import QgsProviderRegistry, QgsDataSourceUri

from functools import partial

from ..widgets.preview_components import PreviewDialog, PreviewWidgetFactory
from ..widgets.qgis_layer_sync_manager import QGISLayerSyncManager
from ..widgets.tree_widget_handler import TreeWidgetHandler
from .info_dialog import InfoDialog
from .import_dialog import ImportDialog
from .export_dialog import ExportDialog

from ...container import DependencyContainer
from ...application import SettingsService
from ...domain.dxf import DxfDocument, EntitySelector
from ...workers.dxf_worker import DXFWorker
from ...workers.long_task_worker import LongTaskWorker
from .connections_manager import ConnectionsManager
from ...localization.localization_manager import LocalizationManager
from ...logger.logger import Logger


# Load UI file from resources
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), '..', 'resources', 'main_dialog.ui'))


class ConverterDialog(QtWidgets.QDialog, FORM_CLASS):
    """
    Главный диалог плагина DXF-PostGIS Converter.
    
    Тонкий координатор, использующий DI-контейнер.
    """
    
    def __init__(
        self, 
        iface, 
        container: Optional[DependencyContainer] = None,
        parent: Optional[QtWidgets.QWidget] = None
    ):
        super().__init__(parent)
        self.setupUi(self)
        
        # Core
        self.iface = iface
        self._container = container or DependencyContainer.instance()
        
        # Services from DI container
        self._settings_service = self._container.settings_service
        self._entity_selector = self._container.entity_selector
        self._export_service = self._container.export_service
        
        # Legacy components (для совместимости)
        self.lm = LocalizationManager.instance()
        self.connections_manager = ConnectionsManager()
        
        # UI Handlers
        self.dxf_tree_widget_handler = TreeWidgetHandler(self.dxf_tree_widget)
        self.db_tree_widget_handler = TreeWidgetHandler(self.db_structure_treewidget)
        self.qgis_sync_manager = QGISLayerSyncManager(self.dxf_tree_widget_handler)
        
        # DXF Handler wrapper (для совместимости с legacy code)
        from ...domain.dxf.dxf_handler import DXFHandler
        self.dxf_handler = DXFHandler(
            self.type_shape, 
            self.type_selection, 
            self.dxf_tree_widget_handler
        )
        
        # Preview
        self.preview_cache: Dict[str, Any] = {}
        self.preview_factory = PreviewWidgetFactory()
        self.plugin_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # Workers
        self.worker: Optional[DXFWorker] = None
        self.long_task_worker: Optional[LongTaskWorker] = None
        self.progress_dialog: Optional[QProgressDialog] = None
        
        # State
        self.layer_filter_list_expanded = False
        self.original_layer_filter_list_geom = self.layer_filter_list.geometry()
        self.original_layer_filter_list_parent = self.layer_filter_list.parentWidget()
        
        # Setup
        self._setup_ui()
        self._connect_signals()
        self._load_settings()
        
        Logger.log_message("MainDialog initialized")
    
    # ========== UI Setup ==========
    
    def _setup_ui(self):
        """Настройка UI."""
        self._update_ui_text()
        
        # Help button
        self.info_button = QPushButton("?", self)
        self.info_button.setFixedSize(25, 25)
        self.info_button.setStyleSheet("""
            QPushButton {
                border-radius: 12px;
                background-color: #007bff;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0056b3; }
        """)
        self.info_button.move(self.width() - 35, 10)
        self.info_button.clicked.connect(self._show_help)
        
        # Event filters
        self.layer_filter_list.installEventFilter(self)
    
    def _connect_signals(self):
        """Подключение сигналов."""
        # Tree sync
        self.dxf_tree_widget_handler.tree_structure_created.connect(
            self.qgis_sync_manager.create_qgis_group_structure
        )
        self.dxf_tree_widget_handler.layer_check_changed.connect(
            self.qgis_sync_manager.sync_layer_from_plugin_to_qgis
        )
        
        # Buttons
        self.export_to_db_button.clicked.connect(self._on_import_to_db)
        self.export_to_file_button.clicked.connect(self._on_export_to_file)
        self.apply_filter_button.clicked.connect(self._apply_layer_filter)
        self.clear_filter_button.clicked.connect(self._clear_layer_filter)
        self.tabWidget.currentChanged.connect(self._on_tab_changed)
        
        # Settings
        self.enable_logging_checkbox.stateChanged.connect(self._toggle_logging)
        self.enable_preview_checkbox.stateChanged.connect(self._toggle_preview)
        self.language_combo.currentTextChanged.connect(self._change_language)
    
    def _load_settings(self):
        """Загрузка настроек."""
        is_logging = self._settings_service.is_logging_enabled()
        self.enable_logging_checkbox.setChecked(is_logging)
        Logger.set_logging_enabled(is_logging)
        
        is_preview = self._settings_service.is_preview_enabled()
        self.enable_preview_checkbox.setChecked(is_preview)
        
        lang = self._settings_service.get_language()
        self.language_combo.setCurrentText(lang)
    
    def _update_ui_text(self):
        """Обновление текстов UI."""
        self.setWindowTitle(self.lm.get_string("UI", "main_dialog_title"))
        
        # Tabs
        self.tabWidget.setTabText(0, self.lm.get_string("UI", "tab_dxf_to_sql"))
        self.tabWidget.setTabText(1, self.lm.get_string("UI", "tab_sql_to_dxf"))
        self.tabWidget.setTabText(2, self.lm.get_string("UI", "tab_settings"))
        
        # Buttons
        self.open_dxf_button.setText(self.lm.get_string("UI", "open_dxf_button"))
        self.select_area_button.setText(self.lm.get_string("UI", "select_area_button"))
        self.export_to_db_button.setText(self.lm.get_string("UI", "export_to_db_button"))
        self.export_to_file_button.setText(self.lm.get_string("UI", "export_to_file_button"))
        
        # Filter
        self.filter_groupbox.setTitle(self.lm.get_string("UI", "selection_filter"))
        self.apply_filter_button.setText(self.lm.get_string("UI", "apply_filter_button"))
        self.clear_filter_button.setText(self.lm.get_string("UI", "clear_filter_button"))
        
        # Settings
        self.language_label.setText(self.lm.get_string("UI", "interface_language"))
        self.enable_logging_checkbox.setText(self.lm.get_string("UI", "enable_logs"))
        self.enable_preview_checkbox.setText(self.lm.get_string("UI", "enable_preview", "Создавать превью при импорте"))
    
    # ========== Event Handlers ==========
    
    def _on_import_to_db(self):
        """Импорт в БД."""
        selected_file = self.dxf_tree_widget_handler.get_selected_file_name()
        if not selected_file:
            QMessageBox.warning(
                self,
                self.lm.get_string("COMMON", "error"),
                self.lm.get_string("MAIN_DIALOG", "no_file_selected")
            )
            return
        
        # Проверяем частичное выделение
        total = self.dxf_handler.len_entities_file.get(selected_file, 0)
        selected = len(self.dxf_handler.selected_entities.get(selected_file, []))
        
        if selected != total:
            result = QMessageBox.question(
                self,
                self.lm.get_string("MAIN_DIALOG", "import_to_db"),
                self.lm.get_string("MAIN_DIALOG", "import_selected_question"),
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if result == QMessageBox.Cancel:
                return
        
        # Открываем диалог импорта
        dialog = ImportDialog(
            self.dxf_handler,
            self.dxf_tree_widget_handler,
            self._container,
            self
        )
        dialog.exec_()
        self._show_window()
    
    def _on_export_to_file(self):
        """Экспорт в файл."""
        selected_file = self.dxf_tree_widget_handler.get_selected_file_name()
        if not selected_file:
            QMessageBox.warning(
                self,
                self.lm.get_string("COMMON", "error"),
                self.lm.get_string("MAIN_DIALOG", "no_file_selected")
            )
            return
        
        entities = self.dxf_handler.selected_entities.get(selected_file, [])
        if not entities:
            QMessageBox.warning(
                self,
                self.lm.get_string("COMMON", "warning"),
                self.lm.get_string("MAIN_DIALOG", "no_entities_selected")
            )
            return
        
        # Диалог сохранения
        output_file, _ = QFileDialog.getSaveFileName(
            self,
            self.lm.get_string("MAIN_DIALOG", "save_dxf_file"),
            f"{os.path.splitext(selected_file)[0]}_selected.dxf",
            "DXF files (*.dxf);;All files (*.*)"
        )
        
        if not output_file:
            return
        
        try:
            from ...application.export_service import ExportEntitiesRequest
            
            # Получаем выбранные сущности
            selected_entities = self.dxf_handler.selected_entities.get(selected_file, [])
            entity_handles = [entity.dxf.handle for entity in selected_entities]
            
            request = ExportEntitiesRequest(
                source_file=selected_file,
                output_file=output_file,
                entity_handles=entity_handles
            )
            
            result = self._export_service.export_selected_entities(
                request=request,
                dxf_handler=self.dxf_handler
            )
            
            if result.success:
                QMessageBox.information(
                    self,
                    self.lm.get_string("COMMON", "success"),
                    self.lm.get_string("MAIN_DIALOG", "export_success", output_file)
                )
            else:
                QMessageBox.critical(
                    self,
                    self.lm.get_string("COMMON", "error"),
                    result.error_message or self.lm.get_string("MAIN_DIALOG", "export_failed")
                )
        except Exception as e:
            Logger.log_error(f"Export error: {e}")
            QMessageBox.critical(self, self.lm.get_string("COMMON", "error"), str(e))
    
    def _on_tab_changed(self, index):
        """Смена вкладки."""
        if index == 1:  # PostGIS → DXF
            self._refresh_db_tree()
    
    def _apply_layer_filter(self):
        """Применить фильтр слоёв."""
        selected_file = self.dxf_tree_widget_handler.get_selected_file_name()
        if not selected_file:
            QMessageBox.warning(
                self,
                self.lm.get_string("COMMON", "warning"),
                self.lm.get_string("MAIN_DIALOG", "no_file_selected")
            )
            return
        
        selected_items = self.layer_filter_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(
                self,
                self.lm.get_string("COMMON", "warning"),
                self.lm.get_string("MAIN_DIALOG", "no_layers_selected")
            )
            return
        
        selected_layers = [item.text() for item in selected_items]
        
        # Применяем фильтр
        self.dxf_tree_widget_handler.updating_selection = True
        self.dxf_tree_widget_handler.batch_update = True
        
        try:
            file_data = self.dxf_tree_widget_handler.tree_items.get(selected_file, {})
            
            for layer_name, layer_data in file_data.items():
                if isinstance(layer_data, dict) and 'item' in layer_data:
                    layer_item = layer_data['item']
                    
                    if layer_name not in selected_layers:
                        layer_item.setCheckState(0, Qt.Unchecked)
                        self.dxf_tree_widget_handler.update_child_check_states(
                            layer_item, Qt.Unchecked
                        )
            
            self.dxf_tree_widget_handler.update_selection_count(selected_file)
            
        finally:
            self.dxf_tree_widget_handler.batch_update = False
            self.dxf_tree_widget_handler.updating_selection = False
        
        self.dxf_tree_widget_handler.selection_changed.emit(selected_file)
        
        QMessageBox.information(
            self,
            self.lm.get_string("COMMON", "success"),
            self.lm.get_string("MAIN_DIALOG", "filter_applied_multiple", ", ".join(selected_layers))
        )
    
    def _clear_layer_filter(self):
        """Очистить фильтр."""
        self.layer_filter_list.clearSelection()
    
    def update_layer_filter_list(self):
        """Обновляет список слоев в списке фильтра."""
        self.layer_filter_list.clear()
        
        file_name = self.dxf_tree_widget_handler.get_selected_file_name()
        if not file_name:
            return
            
        # Получаем список слоев из текущего файла
        if file_name in self.dxf_tree_widget_handler.tree_items:
            file_data = self.dxf_tree_widget_handler.tree_items[file_name]
            for layer_name in file_data.keys():
                if isinstance(file_data[layer_name], dict) and 'item' in file_data[layer_name]:
                    self.layer_filter_list.addItem(layer_name)
    
    def _toggle_logging(self, state):
        """Переключить логирование."""
        enabled = state == Qt.Checked
        self._settings_service.set_logging_enabled(enabled)
        Logger.set_logging_enabled(enabled)
    
    def _toggle_preview(self, state):
        """Переключить создание превью."""
        enabled = state == Qt.Checked
        self._settings_service.set_preview_enabled(enabled)
    
    def _change_language(self, new_lang):
        """Сменить язык."""
        self.lm.set_language(new_lang)
        self._settings_service.set_language(new_lang)
        self._update_ui_text()
    
    def _show_help(self):
        """Показать справку."""
        dialog = InfoDialog(
            self.lm.get_string("MAIN_DIALOG", "help_dialog_title"),
            self.lm.get_string("HELP_CONTENT", "MAIN_DIALOG"),
            self
        )
        dialog.exec_()
    
    def _show_window(self):
        """Показать окно."""
        self.raise_()
        self.activateWindow()
        self.show()
    
    # Используется в плагине dxf_tools (uiADXF2Shape.py 626 строка)
    def read_multiple_dxf(self, file_names):
        """
        Обработка выбора нескольких DXF файлов и заполнение древовидного виджета слоями и объектами.
        """
        self.worker = DXFWorker(self.dxf_handler, file_names)
        self.worker.finished.connect(self.process_results)
        self.worker.error.connect(self.handle_error)
        
        self.worker.start()
        
    def process_results(self, results: list):
        for result in results:
            if result:
                self.dxf_tree_widget_handler.populate_tree_widget(result)
        
        self.export_to_db_button.setEnabled(self.dxf_handler.file_is_open)
        self.export_to_file_button.setEnabled(self.dxf_handler.file_is_open)
        self.select_area_button.setEnabled(self.dxf_handler.file_is_open)
        
        # Обновляем список слоев в комбобоксе фильтра
        self.update_layer_filter_list()


    def handle_error(self, error_message):
        self.progress_dialog.close()
        QMessageBox.critical(self, self.lm.get_string("COMMON", "error"),
                            self.lm.get_string("MAIN_DIALOG", "error_processing_dxf", error_message))

    # ========== Long Task Handling (for select_entities_in_area) ==========
    def start_long_task(self, task_id, func, *args):
        """
        Запускает длительную задачу в отдельном потоке.
        """
        self.long_task_worker = LongTaskWorker(task_id, func, *args)
        self.long_task_worker.finished.connect(self.on_finished)
        self.long_task_worker.error.connect(self.handle_long_task_error)
        
        self.long_task_worker.start()

    def handle_long_task_error(self, error_message):
        """Обработчик ошибок длительных задач"""
        QMessageBox.critical(self, self.lm.get_string("COMMON", "error"), 
                            self.lm.get_string("MAIN_DIALOG", "error_executing_task", error_message))

    def on_finished(self, task_id, result):
        """
        Обрабатывает завершение задачи.
        """
        if result is not None:
            if task_id == "select_entities_in_area" and result != []:
                self.dxf_tree_widget_handler.select_area(result)

        self.export_to_db_button.setEnabled(self.dxf_handler.file_is_open)
        self.export_to_file_button.setEnabled(self.dxf_handler.file_is_open)
        self.select_area_button.setEnabled(self.dxf_handler.file_is_open)

        if hasattr(self, 'long_task_worker') and self.long_task_worker:
            self.long_task_worker.deleteLater()
            self.long_task_worker = None

    # ========== DB Tree ==========
    
    def _refresh_db_tree(self):
        """Обновить дерево БД."""
        self.preview_factory.clear_cache()
        self.db_structure_treewidget.clear()
        
        connections = QgsProviderRegistry.instance().providerMetadata('postgres').connections()
        
        if not connections:
            item = QTreeWidgetItem([self.lm.get_string("MAIN_DIALOG", "no_connections")])
            self.db_structure_treewidget.addTopLevelItem(item)
            return
        
        for conn_name, metadata in connections.items():
            try:
                uri = QgsDataSourceUri(metadata.uri())
                conn_item = QTreeWidgetItem([conn_name])
                self.db_structure_treewidget.addTopLevelItem(conn_item)
                
                # Кнопки
                buttons_widget = QWidget()
                layout = QHBoxLayout(buttons_widget)
                layout.setContentsMargins(20, 0, 0, 0)
                
                connect_btn = QPushButton(self.lm.get_string("MAIN_DIALOG", "connect_button"))
                connect_btn.setFixedSize(80, 20)
                connect_btn.clicked.connect(
                    partial(self._connect_to_db, conn_name, conn_item, uri)
                )
                
                info_btn = QPushButton(self.lm.get_string("MAIN_DIALOG", "info_button"))
                info_btn.setFixedSize(80, 20)
                info_btn.clicked.connect(
                    partial(self._show_db_info, conn_name, uri)
                )
                
                layout.addWidget(connect_btn)
                layout.addWidget(info_btn)
                layout.setAlignment(Qt.AlignLeft)
                
                self.db_structure_treewidget.setItemWidget(conn_item, 1, buttons_widget)
                
            except Exception as e:
                Logger.log_error(f"Error processing connection {conn_name}: {e}")
        
        self.db_structure_treewidget.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.db_structure_treewidget.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
    
    def _connect_to_db(self, conn_name, conn_item, uri):
        """Подключиться к БД."""
        username, password = self.connections_manager.get_credentials(
            uri.host(),
            uri.port(),
            uri.database(),
            default_username=uri.username(),
            parent=self
        )
        
        if not username or not password:
            Logger.log_warning(f"No credentials for {conn_name}")
            return
        
        conn_item.takeChildren()
        
        # Используем репозиторий из контейнера
        from ...application.settings_service import ConnectionSettings
        
        connection = ConnectionSettings(
            host=uri.host(),
            port=uri.port(),
            database=uri.database(),
            username=username,
            password=password
        )
        
        db_conn = self._container.db_connection
        repository = self._container.repository
        
        session = db_conn.connect(connection)
        if not session:
            conn_item.setText(0, f'{conn_name} (connection error)')
            return
        
        try:
            result = repository.find_files_in_schemas(session)
            files = result.get('files', [])
            
            if not files:
                conn_item.setText(0, f'{conn_name} (empty)')
                return
            
            conn_item.setText(0, conn_name)
            
            # Скрываем кнопку подключения
            buttons_widget = self.db_structure_treewidget.itemWidget(conn_item, 1)
            if buttons_widget:
                for child in buttons_widget.findChildren(QPushButton):
                    if child.text() == self.lm.get_string("MAIN_DIALOG", "connect_button"):
                        child.hide()
                        break
            
            conn_display_name = f"{uri.host()}:{uri.port()}/{uri.database()}"
            
            for file_info in files:
                self._add_file_to_tree(conn_item, conn_display_name, uri, file_info)
                
        finally:
            session.close()
    
    def _add_file_to_tree(self, parent_item, conn_display_name, uri, file_info):
        """Добавить файл в дерево."""
        file_item = QTreeWidgetItem([file_info.filename])
        parent_item.addChild(file_item)
        
        buttons_widget = QWidget()
        layout = QHBoxLayout(buttons_widget)
        layout.setContentsMargins(20, 0, 0, 0)
        
        # Превью
        preview_path = os.path.join(
            self.plugin_root_dir, 
            'previews', 
            f"{os.path.splitext(file_info.filename)[0]}.svg"
        )
        
        if os.path.exists(preview_path):
            preview_widget = self.preview_factory.create_preview_widget(
                file_info.filename,
                self.plugin_root_dir,
                self._show_full_preview
            )
            if preview_widget:
                layout.addWidget(preview_widget)
        
        # Кнопки
        for text, callback in [
            (self.lm.get_string("MAIN_DIALOG", "import_button"), 
             partial(self._export_from_db, conn_display_name, uri, file_info)),
            (self.lm.get_string("MAIN_DIALOG", "delete_button"),
             partial(self._delete_from_db, conn_display_name, uri, file_info)),
        ]:
            btn = QPushButton(text)
            btn.setFixedSize(80, 20)
            btn.clicked.connect(callback)
            layout.addWidget(btn)
        
        layout.setAlignment(Qt.AlignLeft)
        self.db_structure_treewidget.setItemWidget(file_item, 1, buttons_widget)
    
    def _show_db_info(self, conn_name, uri):
        """Показать информацию о БД."""
        conn_display_name = f"{uri.host()}:{uri.port()}/{uri.database()}"
        conn = self.connections_manager.get_connection(conn_display_name)
        
        username = conn['username'] if conn else 'N/A'
        password_display = '*' * 8 if conn else 'N/A'
        
        QMessageBox.information(
            self,
            self.lm.get_string("MAIN_DIALOG", "db_info_title"),
            f"Connection: {conn_name}\n"
            f"Database: {uri.database()}\n"
            f"Host: {uri.host()}:{uri.port()}\n"
            f"User: {username}\n"
            f"Password: {password_display}"
        )
    
    def _export_from_db(self, conn_display_name, uri, file_info):
        """Экспорт из БД."""
        dialog = ExportDialog(self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        
        destination = dialog.get_selected_destination()
        conn = self.connections_manager.get_connection(conn_display_name)
        
        if not conn:
            QMessageBox.warning(
                self,
                self.lm.get_string("COMMON", "error"),
                self.lm.get_string("MAIN_DIALOG", "saved_credentials_error")
            )
            return
        
        from ...application.settings_service import ConnectionSettings
        from ...domain.models.config import ExportConfig
        from ...application.export_service import ExportDestination
        
        # Создаём конфигурацию экспорта
        connection_settings = ConnectionSettings(
            host=uri.host(),
            port=uri.port(),
            database=uri.database(),
            username=conn['username'],
            password=conn['password']
        )
        
        export_dest = ExportDestination.QGIS if destination == "qgis" else ExportDestination.FILE
        
        config = ExportConfig(
            connection=connection_settings,
            file_id=file_info.id,
            file_name=file_info.filename,
            destination=export_dest.value
        )
        
        result = self._export_service.export_from_database(config)
        
        if result.success:
            if destination == "qgis":
                self._import_to_qgis(result.output_path, file_info.filename)
            else:
                QMessageBox.information(
                    self,
                    self.lm.get_string("COMMON", "success"),
                    self.lm.get_string("MAIN_DIALOG", "file_saved_successfully", result.output_path)
                )
        else:
            QMessageBox.critical(
                self,
                self.lm.get_string("COMMON", "error"),
                result.message or self.lm.get_string("MAIN_DIALOG", "export_failed")
            )
    
    def _delete_from_db(self, conn_display_name, uri, file_info):
        """Удалить файл из БД."""
        result = QMessageBox.question(
            self,
            self.lm.get_string("MAIN_DIALOG", "delete_file_title"),
            self.lm.get_string("MAIN_DIALOG", "delete_file_question", file_info.filename),
            QMessageBox.Yes | QMessageBox.No
        )
        
        if result != QMessageBox.Yes:
            return
        
        conn = self.connections_manager.get_connection(conn_display_name)
        if not conn:
            return
        
        from ...application.settings_service import ConnectionSettings
        
        connection = ConnectionSettings(
            host=uri.host(),
            port=uri.port(),
            database=uri.database(),
            username=conn['username'],
            password=conn['password']
        )
        
        session = self._container.db_connection.connect(connection)
        if session:
            try:
                self._container.repository.delete_file(session, file_info.id)
                self._refresh_db_tree()
            finally:
                session.close()
    
    def _show_full_preview(self, svg_path):
        """Показать превью."""
        dialog = PreviewDialog(svg_path, self)
        dialog.exec_()
    
    def _import_to_qgis(self, file_path, filename):
        """Импорт в QGIS."""
        try:
            from ...plugins.dxf_tools.uiADXF2Shape import uiADXF2Shape
            plugin = uiADXF2Shape(self)
            success = plugin.import_dxf_programmatically(file_path)
            
            if success:
                QMessageBox.information(
                    self,
                    self.lm.get_string("COMMON", "success"),
                    self.lm.get_string("MAIN_DIALOG", "file_imported_to_qgis", filename)
                )
            
            # Удаляем временный файл
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception:
                pass
                
        except Exception as e:
            Logger.log_error(f"QGIS import error: {e}")
            QMessageBox.critical(self, self.lm.get_string("COMMON", "error"), str(e))
    
    # ========== Events ==========
    
    def eventFilter(self, source, event):
        """Фильтр событий для layer_filter_list."""
        if source == self.layer_filter_list:
            if event.type() == QEvent.FocusIn and not self.layer_filter_list_expanded:
                self.layer_filter_list_expanded = True
                pos = self.layer_filter_list.mapTo(self, self.layer_filter_list.rect().topLeft())
                self.layer_filter_list.setParent(self)
                
                height = self.original_layer_filter_list_geom.height()
                if self.layer_filter_list.count() > 0:
                    content_height = (
                        self.layer_filter_list.sizeHintForRow(0) * 
                        self.layer_filter_list.count() + 
                        2 * self.layer_filter_list.frameWidth()
                    )
                    max_height = self.height() - pos.y() - 10
                    height = min(content_height, max_height)
                
                self.layer_filter_list.setGeometry(
                    pos.x(), pos.y(),
                    self.layer_filter_list.width(), height
                )
                self.layer_filter_list.raise_()
                self.layer_filter_list.show()
                self.layer_filter_list.setFocus()
                
            elif event.type() == QEvent.FocusOut and self.layer_filter_list_expanded:
                self.layer_filter_list_expanded = False
                self.layer_filter_list.setParent(self.original_layer_filter_list_parent)
                self.layer_filter_list.setGeometry(self.original_layer_filter_list_geom)
                self.layer_filter_list.show()
        
        return super().eventFilter(source, event)
    
    def resizeEvent(self, event):
        """Resize event."""
        super().resizeEvent(event)
        if hasattr(self, 'info_button'):
            self.info_button.move(self.width() - 35, 10)
    
    # ========== Legacy compatibility ==========
    
    def check_selected_file(self):
        """Совместимость с legacy code."""
        return self.dxf_tree_widget_handler.get_selected_file_name() is not None
