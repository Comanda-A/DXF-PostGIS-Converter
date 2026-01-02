# -*- coding: utf-8 -*-
"""
Import Dialog - диалог импорта.

Делегирует бизнес-логику ImportService.
Содержит только UI-логику.
"""

import os
import tempfile
import re
from typing import Optional, Dict, Any

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTreeWidget, QLabel, QPushButton, QLineEdit, QWidget,
    QComboBox, QTreeWidgetItem, QProgressDialog, QCheckBox, QMessageBox
)

from ..application import SettingsService, ConnectionSettings, ImportService
from ..application.settings_service import SchemaSettings
from ..domain.models import ImportConfig, ImportResult
from ..container import DependencyContainer
from ..localization.localization_manager import LocalizationManager
from ..logger.logger import Logger
from ..db.connections_manager import ConnectionsManager


class ImportWorker(QThread):
    """Worker thread для импорта."""
    
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    
    def __init__(
        self, 
        import_service: ImportService,
        file_path: str,
        config: ImportConfig,
        entities_by_layer: Optional[Dict] = None
    ):
        super().__init__()
        self.import_service = import_service
        self.file_path = file_path
        self.config = config
        self.entities_by_layer = entities_by_layer
    
    def run(self):
        try:
            result = self.import_service.import_dxf(
                self.file_path,
                self.config,
                self.entities_by_layer,
                progress_callback=lambda p, m: self.progress.emit(p, m)
            )
            self.finished.emit(result.success, result.message)
        except Exception as e:
            self.finished.emit(False, str(e))


class ImportDialog(QDialog):
    """
    Диалог импорта данных из DXF в базу данных.
    
    Делегирует бизнес-логику ImportService.
    """
    
    def __init__(
        self, 
        dxf_handler,  # Пока оставляем для совместимости
        tree_widget_handler,
        container: Optional[DependencyContainer] = None,
        parent=None
    ):
        super().__init__(parent)
        
        # DI
        self._container = container or DependencyContainer.instance()
        self._import_service = self._container.import_service
        self._settings_service = self._container.settings_service
        
        # Legacy handlers (для совместимости)
        self.dxf_handler = dxf_handler
        self.tree_widget_handler = tree_widget_handler
        
        # UI state
        self._connection = ConnectionSettings()
        self._schema_settings = SchemaSettings()
        self._connection_manager = ConnectionsManager()
        self._available_schemas: list = []
        
        # Локализация
        self.lm = LocalizationManager.instance()
        
        # Настройки колонок
        self.column_mapping_configs: Dict[str, Any] = {}
        
        # Workers
        self._import_worker: Optional[ImportWorker] = None
        self._progress_dialog: Optional[QProgressDialog] = None
        self._dots_timer: Optional[QTimer] = None
        self._dots_count = 0
        
        Logger.log_message("Инициализация диалога импорта")
        
        self._setup_ui()
        self._load_settings()
        self._populate_tree_widget()
    
    # ========== UI Setup ==========
    
    def _setup_ui(self):
        """Создание UI."""
        self.setWindowTitle(self.lm.get_string("EXPORT_DIALOG", "title"))
        self.setMinimumSize(800, 600)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # Верхняя панель
        self._setup_top_bar(main_layout)
        
        # Контент
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        self._setup_left_column(content_layout)
        self._setup_right_column(content_layout)
        
        main_layout.addLayout(content_layout)
        
        self._connect_signals()
    
    def _setup_top_bar(self, parent_layout):
        """Верхняя панель с кнопкой помощи."""
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        
        self.info_button = QPushButton("?")
        self.info_button.setFixedSize(30, 30)
        self.info_button.setStyleSheet("""
            QPushButton {
                border-radius: 15px;
                background-color: #007bff;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0056b3; }
        """)
        top_bar.addWidget(self.info_button)
        parent_layout.addLayout(top_bar)
    
    def _setup_left_column(self, parent_layout):
        """Левая колонка — DXF объекты и подключение."""
        left_column = QVBoxLayout()
        
        # DXF объекты
        dxf_group = QGroupBox(self.lm.get_string("EXPORT_DIALOG", "dxf_objects_group"))
        dxf_layout = QVBoxLayout()
        
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setMinimumHeight(300)
        dxf_layout.addWidget(self.tree_widget)
        dxf_group.setLayout(dxf_layout)
        left_column.addWidget(dxf_group)
        
        # Подключение к БД
        conn_group = QGroupBox(self.lm.get_string("EXPORT_DIALOG", "db_connection_group"))
        conn_layout = QVBoxLayout()
        
        # Адрес
        addr_row = QHBoxLayout()
        addr_row.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "address_label")))
        self.address_label = QLabel("none")
        addr_row.addWidget(self.address_label)
        self.select_db_button = QPushButton(self.lm.get_string("EXPORT_DIALOG", "select_db_button"))
        addr_row.addWidget(self.select_db_button)
        conn_layout.addLayout(addr_row)
        
        # Порт
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "port_label")))
        self.port_lineedit = QLineEdit("5432")
        port_row.addWidget(self.port_lineedit)
        conn_layout.addLayout(port_row)
        
        # База данных
        db_row = QHBoxLayout()
        db_row.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "db_name_label")))
        self.dbname_label = QLabel("none")
        db_row.addWidget(self.dbname_label)
        conn_layout.addLayout(db_row)
        
        # Пользователь
        user_row = QHBoxLayout()
        user_row.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "username_label")))
        self.username_label = QLabel("none")
        user_row.addWidget(self.username_label)
        conn_layout.addLayout(user_row)
        
        # Пароль
        pass_row = QHBoxLayout()
        pass_row.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "password_label")))
        self.password_lineedit = QLineEdit()
        self.password_lineedit.setEchoMode(QLineEdit.Password)
        pass_row.addWidget(self.password_lineedit)
        conn_layout.addLayout(pass_row)
        
        conn_group.setLayout(conn_layout)
        left_column.addWidget(conn_group)
        
        left_widget = QWidget()
        left_widget.setLayout(left_column)
        parent_layout.addWidget(left_widget)
    
    def _setup_right_column(self, parent_layout):
        """Правая колонка — настройки импорта."""
        right_column = QVBoxLayout()
        
        right_widget = QWidget()
        right_widget.setMaximumWidth(350)
        right_widget.setMinimumWidth(300)
        
        # Название файла
        filename_group = QGroupBox(self.lm.get_string("EXPORT_DIALOG", "import_settings_group"))
        filename_layout = QVBoxLayout()
        
        filename_layout.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "filename_label", "Название файла:")))
        self.filename_lineedit = QLineEdit()
        self.filename_lineedit.setPlaceholderText("Введите название файла")
        filename_layout.addWidget(self.filename_lineedit)
        
        # Режим маппирования
        filename_layout.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "mapping_mode_label", "Режим:")))
        self.mapping_mode_combo = QComboBox()
        self.mapping_mode_combo.addItem("Всегда перезаписывать", "always_overwrite")
        filename_layout.addWidget(self.mapping_mode_combo)
        
        filename_group.setLayout(filename_layout)
        right_column.addWidget(filename_group)
        
        # Схема слоёв
        layer_schema_group = QGroupBox(self.lm.get_string("EXPORT_DIALOG", "layer_schema_group"))
        layer_schema_layout = QVBoxLayout()
        
        schema_row = QHBoxLayout()
        schema_row.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "layer_schema_label")))
        self.layer_schema_combo = QComboBox()
        self.layer_schema_combo.setMinimumWidth(150)
        schema_row.addWidget(self.layer_schema_combo)
        
        self.create_layer_schema_button = QPushButton("+")
        self.create_layer_schema_button.setMaximumWidth(30)
        schema_row.addWidget(self.create_layer_schema_button)
        layer_schema_layout.addLayout(schema_row)
        
        layer_schema_group.setLayout(layer_schema_layout)
        right_column.addWidget(layer_schema_group)
        
        # Схема файлов
        file_schema_group = QGroupBox(self.lm.get_string("EXPORT_DIALOG", "file_schema_group"))
        file_schema_layout = QVBoxLayout()
        
        self.export_layers_only_checkbox = QCheckBox(
            self.lm.get_string("EXPORT_DIALOG", "import_layers_only")
        )
        file_schema_layout.addWidget(self.export_layers_only_checkbox)
        
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "file_schema_label")))
        self.file_schema_combo = QComboBox()
        self.file_schema_combo.setMinimumWidth(150)
        file_row.addWidget(self.file_schema_combo)
        
        self.create_file_schema_button = QPushButton("+")
        self.create_file_schema_button.setMaximumWidth(30)
        file_row.addWidget(self.create_file_schema_button)
        file_schema_layout.addLayout(file_row)
        
        file_schema_group.setLayout(file_schema_layout)
        right_column.addWidget(file_schema_group)
        
        # Кнопки
        button_layout = QHBoxLayout()
        self.import_button = QPushButton(self.lm.get_string("EXPORT_DIALOG", "import_button"))
        self.import_button.setEnabled(False)
        self.cancel_button = QPushButton(self.lm.get_string("EXPORT_DIALOG", "cancel_button"))
        button_layout.addWidget(self.import_button)
        button_layout.addWidget(self.cancel_button)
        right_column.addLayout(button_layout)
        
        right_column.addStretch()
        
        right_widget.setLayout(right_column)
        parent_layout.addWidget(right_widget)
    
    def _connect_signals(self):
        """Подключение сигналов."""
        self.select_db_button.clicked.connect(self._on_select_db)
        self.port_lineedit.textChanged.connect(self._on_port_changed)
        self.password_lineedit.textChanged.connect(self._on_password_changed)
        self.filename_lineedit.textChanged.connect(self._on_filename_changed)
        
        self.layer_schema_combo.currentTextChanged.connect(self._on_layer_schema_changed)
        self.file_schema_combo.currentTextChanged.connect(self._on_file_schema_changed)
        self.export_layers_only_checkbox.toggled.connect(self._on_layers_only_toggled)
        
        self.import_button.clicked.connect(self._on_import_clicked)
        self.cancel_button.clicked.connect(self.reject)
        self.info_button.clicked.connect(self._show_help)
    
    # ========== Settings ==========
    
    def _load_settings(self):
        """Загрузить сохранённые настройки."""
        self._connection = self._settings_service.get_last_connection()
        self._schema_settings = self._settings_service.get_schema_settings()
        
        self._update_connection_ui()
        
        if self._connection.is_configured:
            self._load_schemas()
    
    def _save_settings(self):
        """Сохранить настройки."""
        self._settings_service.save_last_connection(self._connection)
        self._settings_service.save_schema_settings(self._schema_settings)
    
    def _update_connection_ui(self):
        """Обновить UI подключения."""
        self.address_label.setText(self._connection.host)
        self.port_lineedit.setText(self._connection.port)
        self.dbname_label.setText(self._connection.database)
        self.username_label.setText(self._connection.username)
        self.password_lineedit.setText(self._connection.password)
        
        self.filename_lineedit.setText(self._schema_settings.custom_filename)
        self.export_layers_only_checkbox.setChecked(self._schema_settings.export_layers_only)
        
        self._check_import_enabled()
    
    # ========== Event Handlers ==========
    
    def _on_select_db(self):
        """Выбор базы данных."""
        from .providers_dialog import ProvidersDialog
        
        dlg = ProvidersDialog()
        if dlg.exec_() and dlg.db_tree.currentSchema():
            conn = dlg.db_tree.currentDatabase().connection().db.connector
            
            self._connection.host = conn.host
            self._connection.port = str(conn.port)
            self._connection.database = conn.dbname
            
            # Получаем учётные данные
            username, password = self._connection_manager.get_credentials(
                self._connection.host,
                self._connection.port,
                self._connection.database,
                default_username=conn.user,
                parent=self
            )
            
            if username and password:
                self._connection.username = username
                self._connection.password = password
                self._save_settings()
                self._update_connection_ui()
                self._load_schemas()
    
    def _on_port_changed(self, text):
        self._connection.port = text
    
    def _on_password_changed(self, text):
        self._connection.password = text
        self._check_import_enabled()
    
    def _on_filename_changed(self, text):
        self._schema_settings.custom_filename = text.strip()
    
    def _on_layer_schema_changed(self, text):
        self._schema_settings.layer_schema = text
        self._check_import_enabled()
    
    def _on_file_schema_changed(self, text):
        self._schema_settings.file_schema = text
        self._check_import_enabled()
    
    def _on_layers_only_toggled(self, checked):
        self._schema_settings.export_layers_only = checked
        self.file_schema_combo.setEnabled(not checked)
        self.create_file_schema_button.setEnabled(not checked)
        self._check_import_enabled()
    
    def _check_import_enabled(self):
        """Проверить возможность импорта."""
        can_import = (
            self._connection.is_configured and
            bool(self.layer_schema_combo.currentText()) and
            (self._schema_settings.export_layers_only or bool(self.file_schema_combo.currentText()))
        )
        self.import_button.setEnabled(can_import)
    
    def _load_schemas(self):
        """Загрузить схемы из БД."""
        config = self._build_import_config()
        schemas = self._import_service.get_available_schemas(config)
        
        if not schemas:
            return
        
        self._available_schemas = schemas
        
        # Обновляем комбобоксы
        current_layer = self.layer_schema_combo.currentText() or self._schema_settings.layer_schema
        current_file = self.file_schema_combo.currentText() or self._schema_settings.file_schema
        
        self.layer_schema_combo.clear()
        self.file_schema_combo.clear()
        
        for schema in schemas:
            self.layer_schema_combo.addItem(schema)
            self.file_schema_combo.addItem(schema)
        
        # Восстанавливаем выбор
        idx = self.layer_schema_combo.findText(current_layer)
        if idx >= 0:
            self.layer_schema_combo.setCurrentIndex(idx)
        
        idx = self.file_schema_combo.findText(current_file)
        if idx >= 0:
            self.file_schema_combo.setCurrentIndex(idx)
        
        self._check_import_enabled()
    
    def _show_help(self):
        """Показать справку."""
        from .info_dialog import InfoDialog
        dialog = InfoDialog(
            self.lm.get_string("EXPORT_DIALOG", "help_dialog_title"),
            self.lm.get_string("HELP_CONTENT", "EXPORT_DIALOG"),
            self
        )
        dialog.exec_()
    
    # ========== Import ==========
    
    def _on_import_clicked(self):
        """Обработка нажатия кнопки импорта."""
        self._save_settings()
        
        # Создаём временный файл
        selected_file = self.tree_widget_handler.get_selected_file_name()
        if not selected_file:
            QMessageBox.warning(self, "Ошибка", "Не выбран файл для импорта")
            return
        
        final_filename = self._schema_settings.custom_filename or selected_file
        if not final_filename.lower().endswith('.dxf'):
            final_filename += '.dxf'
        
        # Создаём временный файл
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, final_filename)
        
        if not self.dxf_handler.save_selected_entities(selected_file, temp_file):
            QMessageBox.critical(self, "Ошибка", "Не удалось создать временный файл")
            return
        
        # Получаем сущности для импорта
        entities = self.dxf_handler.get_entities_for_export(selected_file)
        
        # Создаём конфигурацию
        config = self._build_import_config()
        config.custom_filename = final_filename
        
        # Показываем прогресс
        self._show_progress_dialog()
        
        # Запускаем импорт
        self._import_worker = ImportWorker(
            self._import_service,
            temp_file,
            config,
            entities
        )
        self._import_worker.progress.connect(self._update_progress)
        self._import_worker.finished.connect(lambda ok, msg: self._on_import_finished(ok, msg, temp_file))
        self._import_worker.start()
    
    def _build_import_config(self) -> ImportConfig:
        """Построить конфигурацию импорта."""
        return ImportConfig(
            connection=self._connection,
            layer_schema=self.layer_schema_combo.currentText() or 'layer_schema',
            file_schema=self.file_schema_combo.currentText() or 'file_schema',
            mapping_mode=self.mapping_mode_combo.currentData() or 'always_overwrite',
            export_layers_only=self._schema_settings.export_layers_only,
            custom_filename=self._schema_settings.custom_filename,
            column_mappings=self.column_mapping_configs
        )
    
    def _show_progress_dialog(self):
        """Показать диалог прогресса."""
        self._progress_dialog = QProgressDialog(
            self.lm.get_string("EXPORT_DIALOG", "import_progress"),
            None, 0, 100, self
        )
        self._progress_dialog.setWindowModality(Qt.WindowModal)
        self._progress_dialog.setWindowTitle(self.lm.get_string("EXPORT_DIALOG", "import_title"))
        self._progress_dialog.setAutoClose(True)
        self._progress_dialog.setCancelButton(None)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.show()
        
        # Анимация точек
        self._dots_count = 0
        self._dots_timer = QTimer()
        self._dots_timer.timeout.connect(self._animate_progress)
        self._dots_timer.start(500)
    
    def _animate_progress(self):
        """Анимация точек в прогрессе."""
        if self._progress_dialog:
            self._dots_count = (self._dots_count + 1) % 4
            text = self._progress_dialog.labelText().rstrip('.')
            self._progress_dialog.setLabelText(text + '.' * self._dots_count)
    
    def _update_progress(self, percent, message):
        """Обновить прогресс."""
        if self._progress_dialog:
            self._progress_dialog.setValue(percent)
            self._progress_dialog.setLabelText(message)
    
    def _on_import_finished(self, success: bool, message: str, temp_file: str):
        """Обработка завершения импорта."""
        # Останавливаем таймер
        if self._dots_timer:
            self._dots_timer.stop()
        
        # Закрываем прогресс
        if self._progress_dialog:
            self._progress_dialog.close()
        
        # Удаляем временный файл
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception as e:
            Logger.log_warning(f"Не удалось удалить временный файл: {e}")
        
        # Показываем результат
        if success:
            QMessageBox.information(
                self,
                self.lm.get_string("EXPORT_DIALOG", "success_title"),
                message
            )
            self.accept()
        else:
            QMessageBox.critical(
                self,
                self.lm.get_string("EXPORT_DIALOG", "error_title"),
                message
            )
    
    # ========== Tree Widget ==========
    
    def _populate_tree_widget(self):
        """Заполнить дерево выбранными элементами."""
        self.tree_widget.clear()
        
        source_tree = self.tree_widget_handler.tree_widget
        
        for i in range(source_tree.topLevelItemCount()):
            file_item = source_tree.topLevelItem(i)
            
            if file_item.checkState(0) in [Qt.Checked, Qt.PartiallyChecked]:
                new_item = QTreeWidgetItem([file_item.text(0)])
                self.tree_widget.addTopLevelItem(new_item)
                self._copy_checked_items(file_item, new_item)
    
    def _copy_checked_items(self, source, target):
        """Рекурсивно копировать отмеченные элементы."""
        for i in range(source.childCount()):
            child = source.child(i)
            if child.checkState(0) in [Qt.Checked, Qt.PartiallyChecked]:
                new_child = QTreeWidgetItem([child.text(0)])
                target.addChild(new_child)
                self._copy_checked_items(child, new_child)
