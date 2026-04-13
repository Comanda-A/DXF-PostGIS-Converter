# -*- coding: utf-8 -*-

import inject
import os

from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import (
    QMessageBox, QTreeWidgetItem, QPushButton, QWidget, QDialog,
    QHBoxLayout, QHeaderView, QProgressDialog, QListWidgetItem, QFileDialog
)
from qgis.PyQt.QtCore import Qt, QSignalBlocker
from qgis.core import QgsProviderRegistry, QgsDataSourceUri

from functools import partial

from ...application.interfaces import ILocalization, ISettings, ILogger
from ...application.dtos import DXFDocumentDTO
from ...application.events import IAppEvents
from ...application.services import ActiveDocumentService, ConnectionConfigService
from ...application.use_cases import (
    OpenDocumentUseCase,
    SelectEntityUseCase,
    SelectAreaUseCase,
    ExportUseCase,
    DataViewerUseCase,
    SaveSelectedToFileUseCase,
)
from ...presentation.widgets import SelectableDxfTreeHandler
from ...presentation.services import DialogTranslator, AreaSelectionController, ExportTabController
from ...presentation.workers import LongTaskWorker


# Load UI file from resources
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), '.', 'resources', 'main_dialog.ui'))


class ConverterDialog(QDialog, FORM_CLASS):
    """
    Главный диалог плагина DXF-PostGIS Converter.
    """

    @inject.autoparams(
        'open_doc_use_case',
        'select_entity_use_case',
        'select_area_use_case',
        'export_use_case',
        'data_viewer_use_case',
        'save_selected_to_file_use_case',
        'active_doc_service',
        'connection_service',
        'app_events',
        'localization',
        'settings',
        'logger'
    )
    def __init__(
        self, 
        iface,
        open_doc_use_case: OpenDocumentUseCase,
        select_entity_use_case: SelectEntityUseCase,
        select_area_use_case: SelectAreaUseCase,
        export_use_case: ExportUseCase,
        data_viewer_use_case: DataViewerUseCase,
        save_selected_to_file_use_case: SaveSelectedToFileUseCase,
        active_doc_service: ActiveDocumentService,
        connection_service: ConnectionConfigService,
        app_events: IAppEvents,
        localization: ILocalization,
        settings: ISettings,
        logger: ILogger
    ):
        super().__init__()
        self.setupUi(self)
        
        self.iface = iface
        self._open_doc_use_case = open_doc_use_case
        self._select_entity_use_case = select_entity_use_case
        self._export_use_case = export_use_case
        self._data_viewer_use_case = data_viewer_use_case
        self._save_selected_to_file_use_case = save_selected_to_file_use_case
        self._active_doc_service = active_doc_service
        self._connection_service = connection_service
        self._app_events = app_events
        self._localization = localization
        self._settings = settings
        self._logger = logger

        self._export_tab_controller = ExportTabController(
            dialog=self,
            iface=self.iface,
            connection_service=self._connection_service,
            data_viewer_use_case=self._data_viewer_use_case,
            export_use_case=self._export_use_case,
            localization=self._localization,
            logger=self._logger,
        )

        self.area_selection_controller = AreaSelectionController(
            dialog=self,
            iface=self.iface,
            localization=self._localization,
            select_area_use_case=select_area_use_case,
        )
        
        # UI Handlers
        self.tree_widget_handler = SelectableDxfTreeHandler(self.dxf_tree_widget)

        self._selection_layers_file = ""
        self._selection_layers = {}

        # Setup
        self._init_components()
        self._connect_signals()
        self._init_ui()
        
        self._logger.message("MainDialog initialized")
    
    # ========== UI Setup ==========
    
    def _init_components(self):
        """Загрузка настроек."""
        self.logging_check.setChecked(self._logger.is_enabled())
        
        self.language_combo.clear()
        for lang in self._localization.available_languages.values():
            self.language_combo.addItem(lang)

        self.language_combo.setCurrentText(self._localization.language_name)

        self._export_tab_controller.update_connection_combo()
    
    def _init_info_button(self):
        if hasattr(self, "info_button"):
            return
        
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

    def _init_ui(self):
        """Настройка UI."""
        self._update_ui_language()
        self._init_info_button()
        self._switch_ui()

    def _connect_signals(self):
        """Подключение сигналов."""
        
        # Buttons
        self._app_events.on_document_opened.connect(self._on_document_opened)
        self._app_events.on_document_closed.connect(self._on_document_closed)
        self._app_events.on_document_modified.connect(self._on_document_modified)

        self.open_dxf_button.clicked.connect(self._on_open_dxf_button_click)
        self.select_area_button.clicked.connect(self._on_select_area_button_click)
        self.import_dxf_button.clicked.connect(self._on_import_dxf_button_click)
        self.save_dxf_button.clicked.connect(self._on_save_selected_to_file_click)

        self.connection_editor_button.clicked.connect(self._on_connection_editor_button_click)
        self.connection_combo.currentTextChanged.connect(self._on_connection_combo_changed)
        self.schema_combo.currentTextChanged.connect(self._on_schema_combo_changed)
        self.refresh_db_button.clicked.connect(self._refresh_db_files)
        self.export_db_button.clicked.connect(self._on_export_db_to_file)

        self.apply_filter_button.clicked.connect(self._on_apply_filter_button_click)
        self.clear_filter_button.clicked.connect(self._on_clear_filter_button_click)
        self.tabWidget.currentChanged.connect(self._on_tab_changed)

        self.file_filter_combo.currentIndexChanged.connect(self._on_file_filter_combo_changed)
        self.layer_search_edit.textChanged.connect(self._update_layer_filter_list)
        self.file_check.stateChanged.connect(self._on_file_check_changed)

        self.layer_filter_list.itemChanged.connect(self._on_layer_check_changed)

        # Settings
        self.logging_check.stateChanged.connect(self._toggle_logging)
        self.language_combo.currentTextChanged.connect(self._localization.set_language_by_name)

        # Update UI when language changes
        self._app_events.on_language_changed.connect(self._update_ui_language)

    def _update_ui_language(self, code: str = ''):
        """Обновление текстов UI."""
        DialogTranslator().translate(self, "MAIN_DIALOG")

        # Tabs
        self.tabWidget.setTabText(0, self._localization.tr("MAIN_DIALOG", "tab_dxf_to_db"))
        self.tabWidget.setTabText(1, self._localization.tr("MAIN_DIALOG", "tab_db_to_dxf"))
        self.tabWidget.setTabText(2, self._localization.tr("MAIN_DIALOG", "tab_settings"))

        # ComboBox
        self.type_shape.clear()
        self.type_shape.addItem(self._localization.tr("MAIN_DIALOG", "shape_rectangle"))
        self.type_shape.addItem(self._localization.tr("MAIN_DIALOG", "shape_circle"))
        self.type_shape.addItem(self._localization.tr("MAIN_DIALOG", "shape_polygon"))

        self.type_selection.clear()
        self.type_selection.addItem(self._localization.tr("MAIN_DIALOG", "selection_inside"))
        self.type_selection.addItem(self._localization.tr("MAIN_DIALOG", "selection_outside"))
        self.type_selection.addItem(self._localization.tr("MAIN_DIALOG", "selection_intersect"))

        self.selection_mode.clear()
        self.selection_mode.addItem(self._localization.tr("MAIN_DIALOG", "mode_join"))
        self.selection_mode.addItem(self._localization.tr("MAIN_DIALOG", "mode_replace"))
        self.selection_mode.addItem(self._localization.tr("MAIN_DIALOG", "mode_subtract"))
        self.selection_mode.setCurrentIndex(1)

        self._export_tab_controller.update_ui_language()
    
    def _switch_ui(self):
        enable = self._active_doc_service.get_documents_count() > 0
        self.import_dxf_button.setEnabled(True)
        self.save_dxf_button.setEnabled(enable)
        self.filter_group.setEnabled(enable)
        self.selection_group.setEnabled(enable)
        self.dxf_tree_label.setEnabled(enable)
        self.dxf_tree_widget.setEnabled(enable)
        self._export_tab_controller.update_export_ui()

# ========== events ==========
    def refresh_documents_view(self):
        """Полная синхронизация UI-списка документов/слоёв/сущностей."""
        self._switch_ui()
        self._update_file_filter_combo()
        self.tree_widget_handler.rebuild_tree(self._active_doc_service.get_all())
        self._update_file_check()
        self._reset_selection_layers()
    def _on_document_opened(self, document: list[DXFDocumentDTO]):
        self._switch_ui()
        self._update_file_filter_combo()
        self.tree_widget_handler.rebuild_tree(
            self._active_doc_service.get_all()
        )

    def _on_document_closed(self, document: list[DXFDocumentDTO]):
        self._switch_ui()
        self._update_file_filter_combo()
        self.tree_widget_handler.rebuild_tree(
            self._active_doc_service.get_all()
        )

    def _on_document_modified(self, document: list[DXFDocumentDTO]):
        self._update_file_check()
        self._reset_selection_layers()
        self.tree_widget_handler.update_tree()

    # ========== filter_groupbox ==========

    def _reset_selection_layers(self):
        self._selection_layers_file = ""
        self._selection_layers = {}

        filename = self.file_filter_combo.currentText()
        if filename:
            doc = self._active_doc_service.get_document_by_filename(filename)
            if doc:
                self._selection_layers_file = filename
                self._selection_layers = {l.name: l.selected for l in doc.layers}

        self._update_layer_filter_list()

    def _update_file_filter_combo(self):
        filenames = [doc.filename for doc in self._active_doc_service.get_all()]
        current_filename = self.file_filter_combo.currentText()
        
        with QSignalBlocker(self.file_filter_combo):
            self.file_filter_combo.clear()
            for name in filenames:
                self.file_filter_combo.addItem(name)
        
        if current_filename and current_filename in filenames:
            self.file_filter_combo.setCurrentText(current_filename)
        
        self._on_file_filter_combo_changed()

    def _on_file_filter_combo_changed(self, index=None):
        self.layer_search_edit.setText("")
        self._reset_selection_layers()
        self._update_file_check()
    
    def _update_layer_filter_list(self):
        """Обновляет список слоев в списке фильтра."""

        layer_search = self.layer_search_edit.text().strip().lower()
        
        # Блокируем сигналы, чтобы не вызывать события при заполнении
        with QSignalBlocker(self.layer_filter_list):
            self.layer_filter_list.clear()
            
            for name, is_selected in self._selection_layers.items():
                # Если задан поиск и слой не соответствует - пропускаем
                if layer_search and layer_search not in name.lower():
                    continue
                    
                # Создаем элемент с чекбоксом
                item = QListWidgetItem(name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if is_selected else Qt.Unchecked)
                
                self.layer_filter_list.addItem(item)

    def _on_layer_check_changed(self, item):
        """Обработка изменения состояния чекбокса в списке."""
        if not item: return
        layer_name = item.text()
        if not layer_name: return
        # Обновляем состояние в кэше
        state = item.checkState() == Qt.Checked
        self._selection_layers[layer_name] = state

        with QSignalBlocker(self.layer_filter_list):
            for item in self.layer_filter_list.selectedItems():
                if item.text() in self._selection_layers:
                    self._selection_layers[item.text()] = state
                    item.setCheckState(Qt.Checked if state else Qt.Unchecked)

    def _update_file_check(self):
        doc = self._active_doc_service.get_document_by_filename(self.file_filter_combo.currentText())
        with QSignalBlocker(self.file_check):
            self.file_check.setChecked(doc.selected if doc else False)

    def _on_file_check_changed(self, state):
        doc = self._active_doc_service.get_document_by_filename(
            self.file_filter_combo.currentText())
        if doc:
            self._select_entity_use_case.execute_single(doc.id, state == Qt.Checked)

    def _on_apply_filter_button_click(self):
        doc = self._active_doc_service.get_document_by_filename(
            self._selection_layers_file
        )

        if not doc:
            self._logger.error(f"Document by name '{self._selection_layers_file}' not found")
            return

        select_layers = {}

        for layer in doc.layers:
            if layer.name in self._selection_layers:
                value = self._selection_layers[layer.name]
                select_layers[layer.id] = value
        
        self._select_entity_use_case.execute(select_layers)

    def _on_clear_filter_button_click(self):
        self._reset_selection_layers()
        self._update_layer_filter_list()

    # ========== area selection ==========

    def _on_select_area_button_click(self):
        self.area_selection_controller.start_map_selection()

    # ========== open dxf button ==========

    def _on_open_dxf_button_click(self):
        """Открытие DXF файлов с отображением прогресса."""
        from ...plugins.dxf_tools.clsADXF2Shape import clsADXF2Shape
        # Создаем диалог выбора файлов
        adxf2shape = clsADXF2Shape(self)
        adxf2shape.run()
        
        # Получаем выбранные файлы
        selected_files = adxf2shape.get_current_files()
        
        if not selected_files:
            return
        
        # Создаем функцию для загрузки файлов
        def load_dxf_files(files):

            result = self._open_doc_use_case.execute(files)
            if result.is_fail:
                self._logger.error(f"Error loading {files}: {result.error}")
                return []
            return result.value
        
        def _on_dxf_loading_finished(result: object, progress_dialog):
            progress_dialog.close()

        def _on_dxf_loading_error(error: str, progress_dialog):
            self._logger.error(f'error {error}')
            progress_dialog.close()
        
        # Создаем и настраиваем воркер
        self.dxf_loader_worker = LongTaskWorker(load_dxf_files, selected_files)
        
        # Создаем диалог прогресса
        progress_dialog = QProgressDialog(
            "progress", 
            "cancel", 
            0, 0, 
            self
        )
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(True)
        progress_dialog.setAutoReset(True)
        progress_dialog.repaint()
        
        self.dxf_loader_worker.finished.connect(
            lambda task_id, result: _on_dxf_loading_finished(result, progress_dialog)
        )
        self.dxf_loader_worker.error.connect(
            lambda error: _on_dxf_loading_error(error, progress_dialog)
        )
        
        # Подключаем отмену
        #progress_dialog.canceled.connect(self._cancel_dxf_loading)
        
        # Запускаем воркер
        self.dxf_loader_worker.start()
        
        # Показываем диалог прогресса
        progress_dialog.exec_()



    # ========== import button ==========

    def _on_import_dxf_button_click(self):
        #count_selected_files = sum(1 for dto in self._active_doc_service.get_all() if dto.selected)
        #if count_selected_files == 0:
        #    QMessageBox.warning(
        #        self,
        #        self._lm.get_string("COMMON", "error"),
        #        self._lm.get_string("MAIN_DIALOG", "no_file_selected")
        #    )
        #    return
        
        from ...presentation.dialogs import ImportDialog

        dialog = ImportDialog(
            self
        )
        dialog.exec_()

    # ========== export tab ==========

    def _update_connection_combo(self):
        self._export_tab_controller.update_connection_combo()

    def _on_connection_editor_button_click(self):
        self._export_tab_controller.on_connection_editor_button_click()

    def _on_connection_combo_changed(self, name: str):
        self._export_tab_controller.on_connection_combo_changed(name)

    def _on_schema_combo_changed(self, schema_name: str):
        self._export_tab_controller.on_schema_combo_changed(schema_name)

    def _refresh_db_files(self):
        self._export_tab_controller.refresh_db_files()

    def _update_export_ui(self):
        self._export_tab_controller.update_export_ui()

    def _on_export_db_to_file(self):
        """Экспорт PostGIS -> DXF."""
        self._export_tab_controller.on_export_clicked()

    def _on_save_selected_to_file_click(self):
        """Сохранить выделенные сущности текущего DXF в новый файл."""
        current_filename = self.file_filter_combo.currentText().strip()
        if not current_filename:
            QMessageBox.information(
                self,
                "Информация",
                self._localization.tr("MAIN_DIALOG", "select_file_first"),
            )
            return

        default_name = os.path.splitext(current_filename)[0] + "_selected.dxf"
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            self._localization.tr("MAIN_DIALOG", "save_as"),
            default_name,
            "DXF Files (*.dxf)",
        )
        if not output_path:
            return

        if not output_path.lower().endswith(".dxf"):
            output_path = output_path + ".dxf"

        def save_task():
            return self._save_selected_to_file_use_case.execute(current_filename, output_path)

        def _on_save_finished(result: object, progress_dialog):
            progress_dialog.close()
            app_result, report = result
            self._logger.message(report)

            if app_result.is_fail:
                QMessageBox.critical(self, "Ошибка", f"Сохранение завершилось с ошибкой: {app_result.error}")
                return

            QMessageBox.information(
                self,
                "Успех",
                self._localization.tr("MAIN_DIALOG", "export_success_folder", os.path.dirname(output_path)),
            )

        def _on_save_error(error: str, progress_dialog):
            progress_dialog.close()
            QMessageBox.critical(self, "Ошибка", f"Ошибка сохранения: {error}")

        self.save_selected_worker = LongTaskWorker(save_task)

        progress_dialog = QProgressDialog(
            self._localization.tr("MAIN_DIALOG", "export_in_progress"),
            self._localization.tr("MAIN_DIALOG", "cancel"),
            0,
            0,
            self,
        )
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(True)
        progress_dialog.setAutoReset(True)
        progress_dialog.repaint()

        self.save_selected_worker.finished.connect(
            lambda task_id, result: _on_save_finished(result, progress_dialog)
        )
        self.save_selected_worker.error.connect(
            lambda error: _on_save_error(error, progress_dialog)
        )

        self.save_selected_worker.start()
        progress_dialog.exec_()
    
    def _on_tab_changed(self, index):
        """Смена вкладки."""
        if index == 1:  # PostGIS → DXF
            self._export_tab_controller.on_tab_activated()
    
    def _toggle_logging(self, state):
        """Переключить логирование."""
        enabled = state == Qt.Checked
        self._logger.set_enabled(enabled)
    
    def _show_help(self):
        """Показать справку."""
        QMessageBox.information(
            self,
            self._localization.tr("MAIN_DIALOG", "help_dialog_title"),
            self._localization.tr("HELP_CONTENT", "MAIN_DIALOG"),
        )
    
    def _show_window(self):
        """Показать окно."""
        self.raise_()
        self.activateWindow()
        self.show()
    
    def _show_full_preview(self, svg_path):
        """Показать превью."""
        pass

    # ========== Events ==========
    
    def resizeEvent(self, event):
        """Resize event."""
        super().resizeEvent(event)
        if hasattr(self, 'info_button'):
            self.info_button.move(self.width() - 35, 10)
