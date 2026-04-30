from __future__ import annotations

import inject
import os
import tempfile

from qgis.PyQt import uic
from PyQt5.QtCore import Qt, QSignalBlocker
from PyQt5.QtWidgets import (
    QDialog, QPushButton, QProgressDialog, QMessageBox, QInputDialog, QLineEdit
)
from ...application.services import ConnectionConfigService
from ...application.services import ActiveDocumentService
from ...application.interfaces import ILocalization, ILogger
from ...application.dtos import ConnectionConfigDTO, ImportConfigDTO, ImportMode, LayerSettingsDTO, DXFLayerDTO
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
        'connection_service',
        'import_use_case',
        'localization',
        'logger'
    )
    def __init__(
        self,
        parent,
        active_doc_service: ActiveDocumentService,
        connection_service: ConnectionConfigService,
        session: DBSession,
        import_use_case: ImportUseCase,
        localization: ILocalization,
        logger: ILogger
    ):
        super().__init__(parent)
        self.setupUi(self)

        self._active_doc_service = active_doc_service
        self._connection_service = connection_service
        self._session = session
        self._import_use_case = import_use_case
        self._localization = localization
        self._logger = logger

        self._tree_widget_handler = ViewerDxfTreeHandler(self.dxf_files_tree)
        self._connection_config: ConnectionConfigDTO | None = None
        self._import_configs: list[ImportConfigDTO] = []
        self._selected_layer_name: str | None = None  # Для отслеживания выбранного слоя
        
        self._init_components()
        self._connect_signals()
        self._setup_ui()
    
    @property
    def processed_filename(self) -> str | None:
        """Получить название файла независимо от выбранного элемента (файл или слой)"""
        return self._get_selected_file_name()

    @property
    def processed_config(self) -> ImportConfigDTO | None:
        filename = self.processed_filename
        if not filename:
            return None
        for config in self._import_configs:
            if config.filename == filename:
                return config
        return None
    
    def _get_selected_item_type(self) -> str | None:
        """
        Определить тип выбранного элемента.
        Возвращает: 'file' для файла, 'layer' для слоя, None если ничего не выбрано
        """
        selected_items = self.dxf_files_tree.selectedItems()
        if len(selected_items) == 1:
            item = selected_items[0]
            # Если у элемента есть parent, то это слой
            if item.parent():
                return 'layer'
            # Иначе это файл
            return 'file'
        return None
    
    def _get_selected_layer_name(self) -> str | None:
        """Получить название выбранного слоя"""
        selected_items = self.dxf_files_tree.selectedItems()
        if len(selected_items) == 1:
            item = selected_items[0]
            if item.parent():  # Если это слой
                return item.text(0)
        return None
    
    def _get_selected_file_name(self) -> str | None:
        """Получить название выбранного файла"""
        selected_items = self.dxf_files_tree.selectedItems()
        if len(selected_items) == 1:
            item = selected_items[0]
            if not item.parent():  # Если это файл
                return item.text(0)
            else:  # Если это слой, вернуть названия файла
                parent = item.parent()
                return parent.text(0)
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
        self.connection_editor_button.clicked.connect(self._on_connection_editor_button_click)
        self.connection_combo.currentTextChanged.connect(self._on_connection_combo_changed)
        self.create_layers_schema_button.clicked.connect(self._on_create_schema_button_click)
        self.create_files_schema_button.clicked.connect(self._on_create_schema_button_click)
        self.dxf_files_tree.itemSelectionChanged.connect(self.handle_item_selection)
        self.import_mode_combo.currentTextChanged.connect(self._on_import_mode_combo_changed)
        self.layers_schema_combo.currentTextChanged.connect(self._on_layers_schema_combo_changed)
        self.files_schema_combo.currentTextChanged.connect(self._on_files_schema_combo_changed)
        self.import_only_layers_check.stateChanged.connect(self._on_import_only_layers_check_changed)
        self.import_button.clicked.connect(self._on_import_button_click)
        self.cancel_button.clicked.connect(self._on_cancel_button_click)
        self.transliteration_check.stateChanged.connect(self._on_transliteration_check_changed)
        self.prefix_check.stateChanged.connect(self._on_prefix_check_changed)
        
        # Сигналы для страницы 2 (layer settings)
        self.new_layer_table_check.stateChanged.connect(self._on_new_layer_table_check_changed)
        self.existing_layer_table_check.stateChanged.connect(self._on_existing_layer_table_check_changed)

        self.db_table_combo.currentTextChanged.connect(self._on_db_table_combo_changed)
        self.layer_name_edit.textChanged.connect(self._on_layer_name_edit_changed)

    def _setup_ui(self):
        """Настройка UI."""
        self.import_only_layers_hint_label.setVisible(False)
        self._update_ui_language()
        self._init_info_button()
        self._update_connection_combo()
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
        item_type = self._get_selected_item_type()
        
        enable = bool(item_type and self._session.is_connected)
        self.import_settings_group.setEnabled(False)
        self.layers_schema_group.setEnabled(False)
        self.files_schema_group.setEnabled(False)
        self.layer_import_group.setEnabled(False)
        self.layer_table_db_group.setEnabled(False)
        self.cancel_button.setEnabled(enable)
        self.import_button.setEnabled(enable)

        if enable and item_type == 'file':
            # Показать страницу 1 (настройки файла)
            self.stackedWidget.setCurrentIndex(0)
            config = self.processed_config
            
            if config:
                self.import_settings_group.setEnabled(True)
                self.layers_schema_group.setEnabled(True)
                self.files_schema_group.setEnabled(True)
                
                self.filename_edit.setText(config.filename)
                self.import_only_layers_check.setChecked(config.import_layers_only)
                self.transliteration_check.setChecked(config.transliterate_layer_names)
                self.prefix_check.setChecked(config.prefix_check)

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
                    if self.layers_schema_combo.count() > 0:
                        self.layers_schema_combo.setCurrentIndex(0)
                        self.processed_config.layer_schema = self.layers_schema_combo.currentText()
                    else:
                        self.processed_config.layer_schema = ""
                        self.layers_schema_combo.setCurrentIndex(-1)
                
                index = self.files_schema_combo.findText(config.file_schema)
                if index >= 0:
                    self.files_schema_combo.setCurrentIndex(index)
                else:
                    if self.files_schema_combo.count() > 0:
                        self.files_schema_combo.setCurrentIndex(0)
                        self.processed_config.file_schema = self.files_schema_combo.currentText()
                    else:
                        self.processed_config.file_schema = ""
                        self.files_schema_combo.setCurrentIndex(-1)
        
        elif enable and item_type == 'layer':
            # Показать страницу 2 (настройки слоя)
            self.stackedWidget.setCurrentIndex(1)
            layer_name = self._get_selected_layer_name()
            file_name = self._get_selected_file_name()
            config = self.processed_config
            
            if config and layer_name:
                self.layer_import_group.setEnabled(True)
                self.layer_table_db_group.setEnabled(True)
                self._update_layer_settings_ui(layer_name, file_name, config)

    def _update_layer_settings_ui(self, layer_name: str, file_name: str, config: ImportConfigDTO):
        """Обновить UI для настроек слоя"""
        # Установить название слоя
        self.layer_name_value_label.setText(layer_name)
        
        # Получить информацию о слое из документа
        doc = self._active_doc_service.get_document_by_filename(file_name)
        if doc:
            layer: DXFLayerDTO | None = None
            for doclayer in doc.layers:
                if doclayer.name == layer_name:
                    layer = doclayer
            if layer:
                # Установить количество объектов
                entity_count = len(layer.entities)
                self.count_objects_value_label.setText(str(entity_count))
        
        # Обновить список таблиц из выбранной схемы
        self._update_db_tables_combo()
        
        # Получить или создать настройки слоя
        if layer_name not in config.layer_settings:
            config.layer_settings[layer_name] = LayerSettingsDTO(
                layer_name=layer_name,
                create_new_table=True,
                new_table_name=layer_name,
                existing_table_name=""
            )
        
        layer_settings = config.layer_settings[layer_name]
        
        # Обновить UI в соответствии с настройками
        self.new_layer_table_check.setChecked(layer_settings.create_new_table)
        
        # Обновить название новой таблицы
        with QSignalBlocker(self.layer_name_edit):
            self.layer_name_edit.setText(layer_settings.new_table_name)
        
        # Обновить выбор существующей таблицы
        with QSignalBlocker(self.db_table_combo):
            index = self.db_table_combo.findText(layer_settings.existing_table_name)
            if index >= 0:
                self.db_table_combo.setCurrentIndex(index)

    def _connect_to_db(self, config: ConnectionConfigDTO):
        result = self._session.connect(config)
        if not self._session.is_connected:
            # ★ Если учётные данные есть, но подключение не удалось —
            #   значит проблема на стороне сервера (неверный пароль, недоступен хост и т.д.)
            QMessageBox.critical(
                self,
                self.tr("error_title"),
                self.tr("connection_failed_error")
            )
            self._logger.error(
                f"Failed to connect to database with config '{config.name}': {result.error}"
            )
        self._update_db_connection_info()
        self._update_schemas_combo()
        self._update_ui()

    def _update_db_connection_info(self):
        if self._session.is_connected:
            config = self._session.config
            self.dbms_value_label.setText(config.db_type)
            self.address_value_label.setText(config.host)
            self.port_value_label.setText(config.port)
            self.database_name_value_label.setText(config.database)
            self.username_value_label.setText(config.username)
            self.password_value_label.setText('*' * len(config.password))

            with QSignalBlocker(self.connection_combo):
                if config.name and self.connection_combo.findText(config.name) >= 0:
                    self.connection_combo.setCurrentText(config.name)
                else:
                    self.connection_combo.setCurrentIndex(0)

                selected_items = self.dxf_files_tree.selectedItems()
                if not selected_items and self.dxf_files_tree.topLevelItemCount() > 0:
                    self.dxf_files_tree.topLevelItem(0).setSelected(True)
        else:
            self.dbms_value_label.setText("")
            self.address_value_label.setText("-")
            self.port_value_label.setText("-")
            self.database_name_value_label.setText("-")
            self.username_value_label.setText("-")
            self.password_value_label.setText("-")
            with QSignalBlocker(self.connection_combo):
                self.connection_combo.setCurrentIndex(0)
            
            # Deselect first item if it exists
            first_item = self.dxf_files_tree.topLevelItem(0)
            if first_item:
                first_item.setSelected(False)
    
    def _update_connection_combo(self):
        configs = self._connection_service.get_all_configs()
        current_name = self.connection_combo.currentText()

        with QSignalBlocker(self.connection_combo):
            self.connection_combo.clear()
            self.connection_combo.addItem("")
            for config in configs:
                self.connection_combo.addItem(config.name)

            if current_name and self.connection_combo.findText(current_name) >= 0:
                self._connect_to_db(self._connection_service.get_config_by_name(current_name))
            elif configs:
                self.connection_combo.setCurrentIndex(0)

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
        
        # Обновить список таблиц
        self._update_db_tables_combo()

        self._update_ui()
    
    def _update_db_tables_combo(self):
        """Обновить список таблиц в комбо для выбора существующей таблицы слоя"""
        if not self._session.is_connected:
            return
        
        config = self.processed_config
        if not config or not config.layer_schema:
            self.db_table_combo.clear()
            return
        
        # Получить список таблиц из выбранной схемы слоев
        result = self._session.get_tables(config.layer_schema)
        
        if result.is_fail:
            self._logger.error(f"Error getting tables from schema '{config.layer_schema}'. {result.error}")
            return
        
        tables = result.value
        
        with QSignalBlocker(self.db_table_combo):
            current_text = self.db_table_combo.currentText()
            self.db_table_combo.clear()
            self.db_table_combo.addItem("")  # Пустой элемент
            self.db_table_combo.addItems(tables)
            
            # Восстановить выбранное значение если оно есть
            if current_text:
                index = self.db_table_combo.findText(current_text)
                if index >= 0:
                    self.db_table_combo.setCurrentIndex(index)

    # Events

    def _on_connection_editor_button_click(self):
        from ...presentation.dialogs import ConnectionEditorDialog
        dialog = ConnectionEditorDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            if dialog.selected_connection is None:
                return
            self._update_connection_combo()
            self._connect_to_db(dialog.selected_connection)

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
    
    def _on_connection_combo_changed(self, index=None):
        text = self.connection_combo.currentText()

        if not text:
            self._session.close()
            self._update_db_connection_info()
            self._update_schemas_combo()
            self._update_ui()
            return

        config = self._connection_service.get_config_by_name(text)

        if not config:
            QMessageBox.critical(
                self,
                self.tr("error_title"),
                self.tr("connection_config_not_found_error")
            )

            # Сбрасываем комбо обратно на пустой элемент, 
            # чтобы не оставлять невалидный выбор
            with QSignalBlocker(self.connection_combo):
                self.connection_combo.setCurrentIndex(0)

            return

        self._connect_to_db(config)

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
            # Обновить список таблиц при смене схемы
            self._update_db_tables_combo()

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

    def _on_transliteration_check_changed(self, state):
        check = self.transliteration_check.isChecked()
        if self.processed_config:
            self.processed_config.transliterate_layer_names = check

    def _on_prefix_check_changed(self, state):
        check = self.prefix_check.isChecked()
        if self.processed_config:
            self.processed_config.prefix_check = check

    def _on_new_layer_table_check_changed(self, state):
        """Обработчик изменения чекбокса 'Создать новую таблицу'"""
        check = self.new_layer_table_check.isChecked()
        layer_name = self._get_selected_layer_name()
        config = self.processed_config
        
        if layer_name and config and layer_name in config.layer_settings:
            layer_settings = config.layer_settings[layer_name]
            layer_settings.create_new_table = check
            
            with QSignalBlocker(self.existing_layer_table_check):
                self.existing_layer_table_check.setChecked(not check)

            # Обновить видимость элементов
            self.existing_table_widget.setVisible(not check)
            self.new_table_widget.setVisible(check)

    def _on_existing_layer_table_check_changed(self, state):
        """Обработчик изменения чекбокса 'Использовать существующую таблицу'"""
        check = self.existing_layer_table_check.isChecked()
        layer_name = self._get_selected_layer_name()
        config = self.processed_config
        
        if layer_name and config and layer_name in config.layer_settings:
            
            layer_settings = config.layer_settings[layer_name]
            layer_settings.create_new_table = not check

            with QSignalBlocker(self.new_layer_table_check):
                self.new_layer_table_check.setChecked(not check)
            
            # Обновить видимость элементов
            self.existing_table_widget.setVisible(check)
            self.new_table_widget.setVisible(not check)

    def _on_db_table_combo_changed(self, text):
        """Обработчик изменения комбо для выбора существующей таблицы"""
        layer_name = self._get_selected_layer_name()
        config = self.processed_config
        
        if layer_name and config and layer_name in config.layer_settings:
            config.layer_settings[layer_name].existing_table_name = text

    def _on_layer_name_edit_changed(self, text):
        """Обработчик изменения названия новой таблицы слоя"""
        layer_name = self._get_selected_layer_name()
        config = self.processed_config
        
        if layer_name and config and layer_name in config.layer_settings:
            config.layer_settings[layer_name].new_table_name = text

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
            QMessageBox.information(
                self,
                "Информация",
                "Импортирование успешно завершено"
            )

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
        # Деселировать только если выбрано несколько файлов
        with QSignalBlocker(self.dxf_files_tree):
            selected_items = self.dxf_files_tree.selectedItems()
            
            # Если выбрано более одного элемента, оставить только первый
            if len(selected_items) > 1:
                first_item = selected_items[0]
                for item in selected_items[1:]:
                    item.setSelected(False)
                selected_items = [first_item]
            
            # Если выбран элемент и это файл (нет parent), то ок
            # Если это слой (есть parent), то тоже ок
            # Но если выбран только файл и нет слоев, показываем страницу 1
            # Если выбран слой, показываем страницу 2
        
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
    