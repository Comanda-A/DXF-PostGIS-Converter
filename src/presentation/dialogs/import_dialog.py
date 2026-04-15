from __future__ import annotations

import inject
import os
import tempfile

from qgis.PyQt import uic
from PyQt5.QtCore import Qt, QSignalBlocker
from PyQt5.QtWidgets import (
    QDialog, QPushButton, QProgressDialog, QMessageBox, QInputDialog, QLineEdit
)

from ...application.services import ActiveDocumentService
from ...application.interfaces import ILocalization, ILogger
from ...application.dtos import ConnectionConfigDTO, ImportConfigDTO, ImportMode
from ...application.database import DBSession
from ...application.use_cases import ImportUseCase
from ...application.results import AppResult, Unit
from ...presentation.widgets import ViewerDxfTreeHandler
from ...presentation.services import DialogTranslator
from ...presentation.workers import LongTaskWorker




# Load UI file from resources
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), '.', 'resources', 'import_dialog.ui'))

class ImportDialog(QDialog, FORM_CLASS):
    """
    Диалог импорта данных из DXF в базу данных.
    """
    
    @inject.autoparams(
        'active_doc_service',
        'session',
        'import_use_case',
        'localization',
        'logger'
    )
    def __init__(
        self,
        parent,
        active_doc_service: ActiveDocumentService,
        session: DBSession,
        import_use_case: ImportUseCase,
        localization: ILocalization,
        logger: ILogger
    ):
        super().__init__(parent)
        self.setupUi(self)

        self._active_doc_service = active_doc_service
        self._session = session
        self._import_use_case = import_use_case
        self._localization = localization
        self._logger = logger

        self._tree_widget_handler = ViewerDxfTreeHandler(self.dxf_files_tree)
        self._connection_config: ConnectionConfigDTO | None = None
        self._import_configs: list[ImportConfigDTO] = []
        
        self._init_components()
        self._connect_signals()
        self._setup_ui()
    
    @property
    def processed_filename(self) -> str | None:
        selected_items = self.dxf_files_tree.selectedItems()
        if len(selected_items) == 1:
            return selected_items[0].text(0)
        return None

    @property
    def processed_config(self) -> ImportConfigDTO | None:
        filename = self.processed_filename
        for config in self._import_configs:
            if config.filename == filename:
                return config
        return None

    def tr(self, key: str, *args) -> str:
        translated = self._localization.tr("IMPORT_DIALOG", key, *args)
        return translated

    # ========== UI Setup ==========
    
    def _init_components(self):
        docs = self._active_doc_service.get_all()
        for doc in docs:
            self._import_configs.append(
                ImportConfigDTO(
                    filename=doc.filename,
                    import_mode=ImportMode.OVERWRITE_LAYERS,
                    layer_schema="",
                    file_schema="",
                    import_layers_only=False
                )
            )
        self._tree_widget_handler.rebuild_tree(docs, only_selected=True)

    def _connect_signals(self):
        """Подключение сигналов."""
        self.select_database_button.clicked.connect(self._on_select_database_button_click)
        self.create_layers_schema_button.clicked.connect(self._on_create_schema_button_click)
        self.create_files_schema_button.clicked.connect(self._on_create_schema_button_click)
        self.dxf_files_tree.itemSelectionChanged.connect(self.handle_item_selection)
        self.import_mode_combo.currentTextChanged.connect(self._on_import_mode_combo_changed)
        self.layers_schema_combo.currentTextChanged.connect(self._on_layers_schema_combo_changed)
        self.files_schema_combo.currentTextChanged.connect(self._on_files_schema_combo_changed)
        self.import_only_layers_check.stateChanged.connect(self._on_import_only_layers_check_changed)
        self.import_button.clicked.connect(self._on_import_button_click)
        self.cancel_button.clicked.connect(self._on_cancel_button_click)

        #self.filename_lineedit.textChanged.connect(self._on_filename_changed)
        
        #self.layer_schema_combo.currentTextChanged.connect(self._on_layer_schema_changed)
        #self.file_schema_combo.currentTextChanged.connect(self._on_file_schema_changed)
        #self.export_layers_only_checkbox.toggled.connect(self._on_layers_only_toggled)
        
        #self.import_button.clicked.connect(self._on_import_clicked)
        #self.cancel_button.clicked.connect(self.reject)
        #self.info_button.clicked.connect(self._show_help)

    def _setup_ui(self):
        """Настройка UI."""
        self.import_only_layers_hint_label.setVisible(False)
        self._update_ui_language()
        self._init_info_button()
        self._update_ui()
    
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
    
    def _update_ui_language(self):
        """Обновление текстов UI."""
        
        DialogTranslator().translate(self, "IMPORT_DIALOG")
        
        # ComboBox режима маппирования
        with QSignalBlocker(self.import_mode_combo):
            self.import_mode_combo.clear()
            self.import_mode_combo.addItem(self.tr("overwrite_layers"))
            self.import_mode_combo.addItem(self.tr("overwrite_objects"))
            self.import_mode_combo.addItem(self.tr("add_objects"))

    def _update_ui(self):
        enable = bool(self.processed_config and self._session.is_connected)
        self.import_settings_group.setEnabled(enable)
        self.layers_schema_group.setEnabled(enable)
        self.files_schema_group.setEnabled(enable)
        self.cancel_button.setEnabled(enable)
        self.import_button.setEnabled(enable)

        if enable:
            config = self.processed_config
            self.filename_edit.setText(config.filename)
            self.import_only_layers_check.setChecked(config.import_layers_only)

            if config.import_mode == ImportMode.OVERWRITE_LAYERS:
                self.import_mode_combo.setCurrentText(self.tr("overwrite_layers"))
            elif config.import_mode == ImportMode.OVERWRITE_OBJECTS:
                self.import_mode_combo.setCurrentText(self.tr("overwrite_objects"))
            else:
                self.import_mode_combo.setCurrentText(self.tr("add_objects"))

            index = self.layers_schema_combo.findText(config.layer_schema)
            if index >= 0:
                self.layers_schema_combo.setCurrentIndex(index)
            else:
                # Если комбобокс не пустой, устанавливаем первый элемент
                if self.layers_schema_combo.count() > 0:
                    self.layers_schema_combo.setCurrentIndex(0)
                    self.processed_config.layer_schema = self.layers_schema_combo.currentText()
                else:
                    # Если комбобокс пустой, устанавливаем -1 и очищаем конфиг
                    self.processed_config.layer_schema = ""
                    self.layers_schema_combo.setCurrentIndex(-1)
            
            index = self.files_schema_combo.findText(config.file_schema)
            if index >= 0:
                self.files_schema_combo.setCurrentIndex(index)
            else:
                # Если комбобокс не пустой, устанавливаем первый элемент
                if self.files_schema_combo.count() > 0:
                    self.files_schema_combo.setCurrentIndex(0)
                    self.processed_config.file_schema = self.files_schema_combo.currentText()
                else:
                    # Если комбобокс пустой, устанавливаем -1 и очищаем конфиг
                    self.processed_config.file_schema = ""
                    self.files_schema_combo.setCurrentIndex(-1)

    def _update_db_connection_info(self):
        if self._session.is_connected:
            config = self._session.config
            self.dbms_label.setText(config.db_type)
            self.address_value_label.setText(config.host)
            self.port_value_label.setText(config.port)
            self.database_name_value_label.setText(config.database)
            self.username_value_label.setText(config.username)
            self.password_value_label.setText('*' * len(config.password))
        else:
            self.dbms_label.setText("")
            self.address_value_label.setText("-")
            self.port_value_label.setText("-")
            self.database_name_value_label.setText("-")
            self.username_value_label.setText("-")
            self.password_value_label.setText("-")

    def _update_schemas_combo(self):
        
        if not self._session.is_connected:
            return

        result = self._session.get_schemas()

        if result.is_fail:
            self._logger.error(f"Error updating schemas. {result.error}")
            return
        
        schemas = result.value

        self.layers_schema_combo.clear()
        self.files_schema_combo.clear()

        self.layers_schema_combo.addItems(schemas)
        self.files_schema_combo.addItems(schemas)

        self._update_ui()

    # Events

    def _on_select_database_button_click(self):
        from ...presentation.dialogs import ConnectionEditorDialog
        dialog = ConnectionEditorDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            if dialog.selected_connection is None:
                return
            result = self._session.connect(dialog.selected_connection)
            if result.is_fail:
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    "Не удалось подключиться к базе данных"
                )
                return
            self._update_db_connection_info()
            self._update_schemas_combo()
            self._update_ui()

    def _on_create_schema_button_click(self):
        schema_name, ok = QInputDialog.getText(
            self, self.tr("key"), self.tr("key"), QLineEdit.Normal, ""
        )

        # Если пользователь нажал OK и ввел непустое имя
        if ok and schema_name and schema_name.strip():
            schema_name = schema_name.strip()
            
            try:
                result = self._session.schema_exists(schema_name)
                
                if result.is_fail:
                    self._logger.error(f"Failed verify schema exists. {result.error}")
                    QMessageBox.critical(
                        self,
                        "",
                        "Не удалось проверить существование схемы"
                    )
                    return

                if result.value:
                    QMessageBox.warning(
                        self,
                        "",
                        f"Схема с именем '{schema_name}' уже существует"
                    )
                    return

                # Создаем схему в БД
                result = self._session.create_schema(schema_name)
                
                if result.is_fail:
                    self._logger.error(f"Failed create schema. {result.error}")

                # Обновляем список схем в комбо-боксах
                self._update_schemas_combo()
                
                self._logger.message(f"Schema created successfully: {schema_name}")
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    self._localization.tr("IMPORT_DIALOG", "error_title"),
                    self._localization.tr("IMPORT_DIALOG", "create_schema_error").format(str(e))
                )
        elif ok and not schema_name.strip():
            # Пользователь нажал OK, но имя пустое
            QMessageBox.warning(
                self,
                self._localization.tr("IMPORT_DIALOG", "warning_title"),
                self._localization.tr("IMPORT_DIALOG", "schema_name_empty")
            )
    
    def _on_import_mode_combo_changed(self, index=None):
        text = self.import_mode_combo.currentText()
        mode = ImportMode.OVERWRITE_LAYERS

        if text == self.tr("overwrite_layers"):
            self.import_mode_hint_label.setText(self.tr("overwrite_layers_hint"))
            mode = ImportMode.OVERWRITE_LAYERS
        elif text == self.tr("overwrite_objects"):
            self.import_mode_hint_label.setText(self.tr("overwrite_objects_hint"))
            mode = ImportMode.OVERWRITE_OBJECTS
        else:
            self.import_mode_hint_label.setText(self.tr("add_objects_hint"))
            mode = ImportMode.ADD_OBJECTS

        if self.processed_config:
            self.processed_config.import_mode = mode

    def _on_layers_schema_combo_changed(self, index=None):
        if self.processed_config:
            self.processed_config.layer_schema = self.layers_schema_combo.currentText() or ""

    def _on_files_schema_combo_changed(self, index=None):
        if self.processed_config:
            self.processed_config.file_schema = self.files_schema_combo.currentText() or ""

    def _on_import_only_layers_check_changed(self, state):
        check = self.import_only_layers_check.isChecked()
        self.files_schema_label.setEnabled(not check)
        self.files_schema_combo.setEnabled(not check)
        self.create_files_schema_button.setEnabled(not check)
        self.import_only_layers_hint_label.setVisible(check)
        
        if self.processed_config:
            self.processed_config.import_layers_only = check

    def _on_cancel_button_click(self):
        self.reject()
    
    def _on_import_button_click(self):
        
        # функция для загрузки файлов
        def import_task() -> tuple[AppResult[Unit], str]:
            return self._import_use_case.execute(self._session.config, self._import_configs)
        
        def _on_import_finished(result: tuple[AppResult[Unit], str], progress_dialog):
            res, report = result
            self._logger.message(report)
            progress_dialog.close()

        def _on_import_error(error: str, progress_dialog):
            self._logger.error(f'error {error}')
            QMessageBox.critical(
                    self,
                    "Ошибка",
                    'error. {error}'
                )
            progress_dialog.close()
        
        # Создаем и настраиваем воркер
        self.import_worker = LongTaskWorker(import_task)
        
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
        
        self.import_worker.finished.connect(
            lambda task_id, result: _on_import_finished(result, progress_dialog)
        )
        self.import_worker.error.connect(
            lambda error: _on_import_error(error, progress_dialog)
        )
        
        # Подключаем отмену
        #progress_dialog.canceled.connect(self._cancel_dxf_loading)
        
        # Запускаем воркер
        self.import_worker.start()
        
        # Показываем диалог прогресса
        progress_dialog.exec_()

    def handle_item_selection(self):
        """Обработчик изменения выделения."""
        with QSignalBlocker(self.dxf_files_tree):
            selected_items = self.dxf_files_tree.selectedItems()
            for item in selected_items:
                if item.parent():
                    item.setSelected(False)
            self._update_ui()

    def resizeEvent(self, event):
        """Resize event."""
        super().resizeEvent(event)
        if hasattr(self, 'info_button'):
            self.info_button.move(self.width() - 35, 10)

    def _show_help(self):
        """Показать справку."""
        from .info_dialog import InfoDialog
        dialog = InfoDialog(
            self._localization.tr("IMPORT_DIALOG", "help_dialog_title"),
            self._localization.tr("HELP_CONTENT", "IMPORT_DIALOG"),
            self
        )
        dialog.exec_()
    