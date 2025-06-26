from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                           QTreeWidget, QLabel, QPushButton, QLineEdit, QWidget, 
                           QComboBox, QTreeWidgetItem, QProgressDialog, QCheckBox, QMessageBox)
from qgis.core import QgsSettings, Qgis, QgsApplication

from ..localization.localization_manager import LocalizationManager

from ..db.connections_manager import ConnectionsManager
from ..tree_widget_handler import TreeWidgetHandler
from ..logger.logger import Logger
from ..dxf.dxf_handler import DXFHandler
from ..dxf.dxf_exporter import DXFExporter
from ..db.database import (export_dxf_to_database, get_schemas, create_schema)
from .info_dialog import InfoDialog
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QThread, pyqtSignal, QObject
import os
import tempfile
import re


class LogCapture(QObject):    
    """
    Класс для перехвата логов из QgsMessageLog и передачи их в progress_update
    """    
    log_captured = pyqtSignal(str)  # Сигнал для передачи захваченного лога
    
    def __init__(self):
        super().__init__()
        self.is_capturing = False
        # Подключаемся к сигналу QgsMessageLog через экземпляр
        QgsApplication.messageLog().messageReceived.connect(self.on_message_received)
    
    def start_capture(self):
        """Начать захват логов"""
        self.is_capturing = True
    
    def stop_capture(self):
        """Остановить захват логов"""
        self.is_capturing = False
    
    def on_message_received(self, message, tag, level):
        """
        Обработчик получения нового сообщения в лог
        """
        if self.is_capturing and tag == 'DXF-PostGIS-Converter':
            # Передаем только информационные сообщения как прогресс
            if level == Qgis.Info:
                self.log_captured.emit(message)

class ExportThread(QThread):
    """
    Поток для выполнения экспорта данных в базу данных.
    Работает отдельно от основного потока интерфейса, чтобы не блокировать UI.    """    
    finished = pyqtSignal(bool, str)  # Сигнал: успех/неуспех, сообщение
    
    progress_update = pyqtSignal(int, str)  # Сигнал обновления прогресса: процент, сообщение
    def __init__(self, username, password, address, port, dbname, dxf_handler, file_path, 
                 mapping_mode, layer_schema='layer_schema', file_schema='file_schema', 
                 export_layers_only=False, custom_filename=None, column_mapping_configs=None):
        """
        Инициализация потока экспорта.
        
        :param username: Имя пользователя для подключения к БД
        :param password: Пароль пользователя
        :param address: Адрес сервера БД
        :param port: Порт сервера БД
        :param dbname: Имя базы данных
        :param dxf_handler: Обработчик DXF-файлов
        :param file_path: Путь к DXF-файлу для экспорта
        :param mapping_mode: Режим маппирования слоев (always_overwrite, geometry, notes, both)
        :param layer_schema: Схема для размещения таблиц слоев
        :param file_schema: Схема для размещения таблицы файлов
        :param export_layers_only: Экспортировать только слои (без сохранения файла)
        :param custom_filename: Пользовательское название файла для сохранения в БД
        :param column_mapping_configs: Настройки сопоставления столбцов
        """
        super().__init__()
        self.username = username
        self.password = password
        self.address = address
        self.port = port
        self.dbname = dbname
        self.dxf_handler = dxf_handler
        self.file_path = file_path
        self.mapping_mode = mapping_mode
        self.layer_schema = layer_schema
        self.file_schema = file_schema
        self.export_layers_only = export_layers_only
        self.custom_filename = custom_filename
        self.column_mapping_configs = column_mapping_configs or {}
        self.lm = LocalizationManager.instance()
        
        # Создаем захватчик логов
        self.log_capture = LogCapture()
        self.log_capture.log_captured.connect(self.on_log_captured)

    def on_log_captured(self, message):
        """
        Обработчик захваченного лога - передаем его как прогресс
        """
        # Очищаем сообщение от лишних символов
        clean_message = message.strip()
        
        # Определяем процент прогресса на основе ключевых слов
        percent = 50  # Базовое значение прогресса
        
        if "подключение" in clean_message.lower() or "connecting" in clean_message.lower():
            percent = 10
        elif "создание" in clean_message.lower() or "creating" in clean_message.lower():
            percent = 20
        elif "обработка" in clean_message.lower() or "processing" in clean_message.lower():
            percent = 40
        elif "экспорт" in clean_message.lower() or "export" in clean_message.lower():
            percent = 60
        elif "сохранение" in clean_message.lower() or "saving" in clean_message.lower():
            percent = 80
        elif "завершен" in clean_message.lower() or "complete" in clean_message.lower():
            percent = 100
            
        self.progress_update.emit(percent, clean_message)

    def run(self):
        """
        Основной метод потока. Выполняет экспорт и отправляет сигнал о результате.        """
        try:
            # Начинаем захват логов
            self.log_capture.start_capture()
            
            Logger.log_message(self.lm.get_string("EXPORT_DIALOG", "export_thread_start"))
            Logger.log_message(f"Режим маппирования: {self.mapping_mode}")
            
            result = export_dxf_to_database(
                self.username,
                self.password,
                self.address,
                self.port,
                self.dbname,
                self.dxf_handler,
                self.file_path,
                self.mapping_mode,
                self.layer_schema,
                self.file_schema,
                self.export_layers_only,
                self.custom_filename,
                self.column_mapping_configs
            )
            
            # Останавливаем захват логов
            self.log_capture.stop_capture()
            
            if result:
                Logger.log_message(self.lm.get_string("EXPORT_DIALOG", "export_thread_success"))
                self.finished.emit(True, self.lm.get_string("EXPORT_DIALOG", "export_thread_complete"))
            else:
                Logger.log_error("Экспорт не был завершен успешно")
                self.finished.emit(False, self.lm.get_string("EXPORT_DIALOG", "export_thread_failed"))
        except Exception as e:
            # Останавливаем захват логов в случае ошибки
            self.log_capture.stop_capture()
            Logger.log_error(f"Ошибка при экспорте: {str(e)}")
            self.finished.emit(False, str(e))

class ExportDialog(QDialog):
    """
    Диалог экспорта данных в базу данных.
    Позволяет настраивать экспорт DXF-объектов в PostGIS.
    """
    def __init__(self, dxf_tree_widget_handler: TreeWidgetHandler, dxf_handler: DXFHandler, parent=None):
        """
        Инициализация диалога экспорта.
        
        :param dxf_tree_widget_handler: Обработчик древовидного виджета DXF
        :param dxf_handler: Обработчик DXF-файлов
        :param parent: Родительский виджет
        """
        super().__init__(parent)
        self.dxf_tree_widget_handler = dxf_tree_widget_handler
        self.dxf_handler = dxf_handler
        
        self.lm = LocalizationManager.instance()
        
        # Инициализируем переменные
        self.dlg = None
        self.connection_manager = ConnectionsManager()
        self.all_file_paths = []  # Список всех файловых путей

        # Параметры подключения к БД
        self.address = 'none'
        self.port = '5432'
        self.dbname = 'none'
        self.username = 'none'
        self.password = 'none'
        self.schemaname = 'none'        
        # Параметры схем
        self.layer_schema = 'layer_schema'
        self.file_schema = 'file_schema'
        self.export_layers_only = False
        self.available_schemas = []
          # Название файла для экспорта
        self.custom_filename = ""
        
        # Настройки сопоставления столбцов
        self.column_mapping_configs = {}

        Logger.log_message("Инициализация диалога экспорта")
        self.setup_ui()
        self.load_last_connection()
        
        # Заполняем древовидный виджет выбранными объектами
        self.populate_tree_widget()

    def populate_tree_widget(self):
        """Заполнение древовидного виджета выбранными элементами"""
        Logger.log_message("Заполнение древовидного виджета выбранными элементами")
        # Очищаем tree_widget перед заполнением
        self.tree_widget.clear()

        # Проходим по всем элементам первого дерева
        top_level_count = self.dxf_tree_widget_handler.tree_widget.topLevelItemCount()

        for i in range(top_level_count):
            file_item = self.dxf_tree_widget_handler.tree_widget.topLevelItem(i)

            # Проверяем, отмечен ли файл
            if file_item.checkState(0) in [Qt.Checked, Qt.PartiallyChecked]:
                # Копируем файл в новое дерево
                new_file_item = QTreeWidgetItem([file_item.text(0)])
                self.tree_widget.addTopLevelItem(new_file_item)

                self.copy_checked_items(file_item, new_file_item)

    def copy_checked_items(self, parent_item, new_parent_item):
        """
        Рекурсивная функция для копирования всех отмеченных (Checked) дочерних
        элементов из дерева.

        :param parent_item: Исходный родительский элемент
        :param new_parent_item: Новый родительский элемент для копирования
        """
        # Проходим по всем дочерним элементам
        for i in range(parent_item.childCount()):
            child_item = parent_item.child(i)

            # Если элемент отмечен
            if child_item.checkState(0) in [Qt.Checked, Qt.PartiallyChecked]:
                # Копируем элемент в новое дерево
                new_child_item = QTreeWidgetItem([child_item.text(0)])
                new_parent_item.addChild(new_child_item)

                # Рекурсивно копируем его дочерние элементы
                self.copy_checked_items(child_item, new_child_item)


    def setup_ui(self):
        """Создание и настройка элементов пользовательского интерфейса"""
        Logger.log_message("Настройка интерфейса диалога экспорта")
        
        self.setWindowTitle(self.lm.get_string("EXPORT_DIALOG", "title"))
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)

        # Главный макет с отступами и промежутками
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Верхняя панель с кнопкой информации
        top_bar = QHBoxLayout()
        top_bar.addStretch()  
        
        # Кнопка информации
        self.info_button = QPushButton("?")
        self.info_button.setFixedSize(30, 30)
        self.info_button.setStyleSheet("""
            QPushButton {
                border-radius: 15px;
                background-color: #007bff;
                color: white;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        top_bar.addWidget(self.info_button)
        main_layout.addLayout(top_bar)

        # Контент панели 
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # Левая колонка – для DXF объектов и подключения к базе данных
        left_column = QVBoxLayout()
        left_column.setSpacing(10)
        
        # Группа DXF объектов
        self.dxf_group = QGroupBox(self.lm.get_string("EXPORT_DIALOG", "dxf_objects_group"))
        dxf_layout = QVBoxLayout()
        

        # Добавляем древовидный виджет для отображения структуры выбранного файла
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setColumnCount(1)  # Одна колонка для отображения объектов
        self.tree_widget.setMinimumHeight(300)
        self.tree_widget.setMinimumWidth(400)
        dxf_layout.addWidget(self.tree_widget)
        self.dxf_group.setLayout(dxf_layout)
        left_column.addWidget(self.dxf_group)

        # Группа подключения к базе данных
        self.connection_group = QGroupBox(self.lm.get_string("EXPORT_DIALOG", "db_connection_group"))
        conn_layout = QVBoxLayout()
        
        # Строка адреса
        addr_layout = QHBoxLayout()
        self.address_label = QLabel()
        self.select_db_button = QPushButton(self.lm.get_string("EXPORT_DIALOG", "select_db_button"))
        addr_layout.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "address_label")))
        addr_layout.addWidget(self.address_label)
        addr_layout.addWidget(self.select_db_button)
        conn_layout.addLayout(addr_layout)
        
        # Строка порта
        port_layout = QHBoxLayout()
        self.port_lineedit = QLineEdit()
        port_layout.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "port_label")))
        port_layout.addWidget(self.port_lineedit)
        conn_layout.addLayout(port_layout)
        
        # Строка имени БД
        db_layout = QHBoxLayout()
        self.dbname_label = QLabel()
        db_layout.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "db_name_label")))
        db_layout.addWidget(self.dbname_label)
        conn_layout.addLayout(db_layout)
        
        # Строка схемы
        schema_layout = QHBoxLayout()
        self.schema_label = QLabel()
        schema_layout.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "schema_label")))
        schema_layout.addWidget(self.schema_label)
        conn_layout.addLayout(schema_layout)
        
        # Строка имени пользователя
        user_layout = QHBoxLayout()
        self.username_label = QLabel()
        user_layout.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "username_label")))
        user_layout.addWidget(self.username_label)
        conn_layout.addLayout(user_layout)
        
        # Строка пароля
        pass_layout = QHBoxLayout()
        self.password_lineedit = QLineEdit()
        self.password_lineedit.setEchoMode(QLineEdit.Password)  # Скрываем ввод пароля
        pass_layout.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "password_label")))
        pass_layout.addWidget(self.password_lineedit)
        conn_layout.addLayout(pass_layout)
        
        self.connection_group.setLayout(conn_layout)
        left_column.addWidget(self.connection_group)
        
        # Добавляем левую колонку в основной макет с растяжением
        left_widget = QWidget()
        left_widget.setLayout(left_column)
        content_layout.addWidget(left_widget)

        # Правая колонка – для информации и кнопок
        right_column = QVBoxLayout()
        right_column.setSpacing(10)
        
        # Контейнер для правой колонки с фиксированной шириной
        right_widget = QWidget()
        right_widget.setMaximumWidth(350)  # Фиксированная максимальная ширина
        right_widget.setMinimumWidth(300)  # Минимальная ширина
        right_widget.setLayout(right_column)        
        
        # Группа настроек экспорта
        self.export_settings_group = QGroupBox(self.lm.get_string("EXPORT_DIALOG", "export_settings_group"))
        export_settings_layout = QVBoxLayout()
        
        # Поле для ввода названия файла
        filename_layout = QVBoxLayout()
        filename_label = QLabel(self.lm.get_string("EXPORT_DIALOG", "filename_label", "Название файла:"))
        filename_label.setWordWrap(True)
        filename_layout.addWidget(filename_label)
        
        self.filename_lineedit = QLineEdit()
        self.filename_lineedit.setPlaceholderText(self.lm.get_string("EXPORT_DIALOG", "filename_placeholder", "Введите название файла"))
        filename_layout.addWidget(self.filename_lineedit)
        
        # Описание поля названия файла
        filename_description = QLabel(self.lm.get_string("EXPORT_DIALOG", "filename_description", "Оставьте пустым для использования оригинального названия файла"))
        filename_description.setWordWrap(True)
        filename_description.setStyleSheet("color: #666666; font-style: italic; font-size: 11px;")
        filename_layout.addWidget(filename_description)
        
        export_settings_layout.addLayout(filename_layout)
        
        # Добавляем разделитель
        export_settings_layout.addSpacing(10)
        
        # Добавляем группу настроек маппирования слоев
        mapping_group_layout = QVBoxLayout()
        mapping_label = QLabel(self.lm.get_string("EXPORT_DIALOG", "mapping_mode_label", "Режим маппирования слоев:"))
        mapping_label.setWordWrap(True)
        mapping_group_layout.addWidget(mapping_label)
        
        # Комбобокс для выбора режима маппирования
        self.mapping_mode_combo = QComboBox()
        self.mapping_mode_combo.addItem(self.lm.get_string("EXPORT_DIALOG", "mapping_mode_always_overwrite", "Всегда перезаписывать"), "always_overwrite")
        #TODO: this
        #self.mapping_mode_combo.addItem(self.lm.get_string("EXPORT_DIALOG", "mapping_mode_geometry", "Маппирование по геометрии"), "geometry")
        #self.mapping_mode_combo.addItem(self.lm.get_string("EXPORT_DIALOG", "mapping_mode_notes", "Маппирование по примечаниям"), "notes")
        #self.mapping_mode_combo.addItem(self.lm.get_string("EXPORT_DIALOG", "mapping_mode_both", "Маппирование по геометрии и примечаниям"), "both")
        mapping_group_layout.addWidget(self.mapping_mode_combo)
        
        # Описание выбранного режима маппирования
        self.mapping_description = QLabel()
        self.mapping_description.setWordWrap(True)
        self.mapping_description.setStyleSheet("color: #666666; font-style: italic;")
        mapping_group_layout.addWidget(self.mapping_description)

        # НОВОЕ: Настройки сопоставления столбцов
        column_mapping_layout = QHBoxLayout()
        self.enable_column_mapping_checkbox = QCheckBox("Включить сопоставление столбцов")
        self.enable_column_mapping_checkbox.setToolTip("Настройка сопоставления полей DXF с существующими столбцами в БД")
        self.enable_column_mapping_checkbox.toggled.connect(self.on_column_mapping_toggled)
        column_mapping_layout.addWidget(self.enable_column_mapping_checkbox)

        self.configure_mapping_button = QPushButton("Настроить сопоставление")
        self.configure_mapping_button.clicked.connect(self.configure_column_mapping)
        self.configure_mapping_button.setEnabled(False)
        column_mapping_layout.addWidget(self.configure_mapping_button)
        mapping_group_layout.addLayout(column_mapping_layout)

        #self.export_settings_group.setLayout(export_settings_layout)
        #export_settings_layout = QVBoxLayout()

        # Обновляем описание при инициализации
        self.update_mapping_description(0)
        
        export_settings_layout.addLayout(mapping_group_layout)
        
        # Добавляем разделитель
        export_settings_layout.addSpacing(10)
        
        # Информация о сравнении геометрии
        mapping_info_label = QLabel(self.lm.get_string("EXPORT_DIALOG", "mapping_info"))
        mapping_info_label.setWordWrap(True)
        export_settings_layout.addWidget(mapping_info_label)
        
        self.export_settings_group.setLayout(export_settings_layout)
        right_column.addWidget(self.export_settings_group)
        
        # Группа настроек схемы для слоев
        self.layer_schema_group = QGroupBox(self.lm.get_string("EXPORT_DIALOG", "layer_schema_group"))
        layer_schema_layout = QVBoxLayout()
        
        # Выбор схемы для слоев
        layer_schema_select_layout = QHBoxLayout()
        layer_schema_select_layout.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "layer_schema_label")))
        
        self.layer_schema_combo = QComboBox()
        self.layer_schema_combo.setMinimumWidth(150)
        layer_schema_select_layout.addWidget(self.layer_schema_combo)
        
        # Кнопка создания новой схемы для слоев
        self.create_layer_schema_button = QPushButton("+")
        self.create_layer_schema_button.setMaximumWidth(30)
        self.create_layer_schema_button.setToolTip(self.lm.get_string("EXPORT_DIALOG", "create_new_schema"))
        layer_schema_select_layout.addWidget(self.create_layer_schema_button)
        
        layer_schema_layout.addLayout(layer_schema_select_layout)
        
        # Поле для ввода имени новой схемы слоев
        self.layer_schema_name_layout = QHBoxLayout()
        self.layer_schema_name_label = QLabel(self.lm.get_string("EXPORT_DIALOG", "new_schema_name"))
        self.layer_schema_name_input = QLineEdit()
        self.layer_schema_name_input.setPlaceholderText("schema_name")
        self.confirm_layer_schema_button = QPushButton("✓")
        self.confirm_layer_schema_button.setMaximumWidth(30)
        self.cancel_layer_schema_button = QPushButton("✗")
        self.cancel_layer_schema_button.setMaximumWidth(30)
        
        self.layer_schema_name_layout.addWidget(self.layer_schema_name_label)
        self.layer_schema_name_layout.addWidget(self.layer_schema_name_input)
        self.layer_schema_name_layout.addWidget(self.confirm_layer_schema_button)
        self.layer_schema_name_layout.addWidget(self.cancel_layer_schema_button)
        
        # Скрываем поля для создания новой схемы по умолчанию
        self.layer_schema_name_widget = QWidget()
        self.layer_schema_name_widget.setLayout(self.layer_schema_name_layout)
        self.layer_schema_name_widget.setVisible(False)
        layer_schema_layout.addWidget(self.layer_schema_name_widget)
        
        self.layer_schema_group.setLayout(layer_schema_layout)
        right_column.addWidget(self.layer_schema_group)
        
        # Группа настроек схемы для файлов
        self.file_schema_group = QGroupBox(self.lm.get_string("EXPORT_DIALOG", "file_schema_group"))
        file_schema_layout = QVBoxLayout()
        
        # Чекбокс "Экспортировать только слои"
        self.export_layers_only_checkbox = QCheckBox(self.lm.get_string("EXPORT_DIALOG", "export_layers_only"))
        file_schema_layout.addWidget(self.export_layers_only_checkbox)
        
        # Выбор схемы для файлов (активен только когда чекбокс не выбран)
        file_schema_select_layout = QHBoxLayout()
        file_schema_select_layout.addWidget(QLabel(self.lm.get_string("EXPORT_DIALOG", "file_schema_label")))
        
        self.file_schema_combo = QComboBox()
        self.file_schema_combo.setMinimumWidth(150)
        file_schema_select_layout.addWidget(self.file_schema_combo)
        
        # Кнопка создания новой схемы для файлов
        self.create_file_schema_button = QPushButton("+")
        self.create_file_schema_button.setMaximumWidth(30)
        self.create_file_schema_button.setToolTip(self.lm.get_string("EXPORT_DIALOG", "create_new_schema"))
        file_schema_select_layout.addWidget(self.create_file_schema_button)
        
        file_schema_layout.addLayout(file_schema_select_layout)
        
        # Поле для ввода имени новой схемы файлов
        self.file_schema_name_layout = QHBoxLayout()
        self.file_schema_name_label = QLabel(self.lm.get_string("EXPORT_DIALOG", "new_schema_name"))
        self.file_schema_name_input = QLineEdit()
        self.file_schema_name_input.setPlaceholderText("schema_name")
        self.confirm_file_schema_button = QPushButton("✓")
        self.confirm_file_schema_button.setMaximumWidth(30)
        self.cancel_file_schema_button = QPushButton("✗")
        self.cancel_file_schema_button.setMaximumWidth(30)
        
        self.file_schema_name_layout.addWidget(self.file_schema_name_label)
        self.file_schema_name_layout.addWidget(self.file_schema_name_input)
        self.file_schema_name_layout.addWidget(self.confirm_file_schema_button)
        self.file_schema_name_layout.addWidget(self.cancel_file_schema_button)
        
        # Скрываем поля для создания новой схемы по умолчанию
        self.file_schema_name_widget = QWidget()
        self.file_schema_name_widget.setLayout(self.file_schema_name_layout)
        self.file_schema_name_widget.setVisible(False)
        file_schema_layout.addWidget(self.file_schema_name_widget)
        
        self.file_schema_group.setLayout(file_schema_layout)
        right_column.addWidget(self.file_schema_group)
        
        # Кнопки внизу правой колонки
        button_layout = QHBoxLayout()
        self.export_button = QPushButton(self.lm.get_string("EXPORT_DIALOG", "export_button"))
        self.export_button.setEnabled(False)  # Изначально неактивна
        self.cancel_button = QPushButton(self.lm.get_string("EXPORT_DIALOG", "cancel_button"))
        
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(self.cancel_button)
        right_column.addLayout(button_layout)
        
        # Добавляем разделитель, чтобы прижать все к верху
        right_column.addStretch()
        
        # Добавляем правый виджет в основной макет
        content_layout.addWidget(right_widget)

        # Добавляем основной макет в окно
        main_layout.addLayout(content_layout)

        # Подключение сигналов
        self._connect_signals()
          # Инициализация состояния элементов
        self.on_export_layers_only_toggled(self.export_layers_only)

    def _connect_signals(self):
        """Подключение всех сигналов пользовательского интерфейса"""
        Logger.log_message("Подключение сигналов интерфейса")
        self.select_db_button.clicked.connect(self.on_select_db_button_clicked)
        self.info_button.clicked.connect(self.show_info_dialog)
        self.port_lineedit.textChanged.connect(self.on_port_changed)
        self.password_lineedit.textChanged.connect(self.on_password_changed)
        self.filename_lineedit.textChanged.connect(self.on_filename_changed)
        self.export_button.clicked.connect(self.on_export_clicked)
        self.cancel_button.clicked.connect(self.on_cancel_clicked)
        # Подключаем сигнал изменения режима маппирования
        self.mapping_mode_combo.currentIndexChanged.connect(self.update_mapping_description)
          # Сигналы для схем
        self.layer_schema_combo.currentTextChanged.connect(self.on_layer_schema_changed)
        self.file_schema_combo.currentTextChanged.connect(self.on_file_schema_changed)
        # Повторная загрузка схем при открытии выпадающего списка
        self.layer_schema_combo.showPopup = self.on_layer_schema_popup
        self.file_schema_combo.showPopup = self.on_file_schema_popup
        self.create_layer_schema_button.clicked.connect(self.show_layer_schema_creation)
        self.create_file_schema_button.clicked.connect(self.show_file_schema_creation)
        self.confirm_layer_schema_button.clicked.connect(self.create_layer_schema)
        self.cancel_layer_schema_button.clicked.connect(self.hide_layer_schema_creation)
        self.confirm_file_schema_button.clicked.connect(self.create_file_schema)
        self.cancel_file_schema_button.clicked.connect(self.hide_file_schema_creation)
        self.export_layers_only_checkbox.toggled.connect(self.on_export_layers_only_toggled)
        self.enable_column_mapping_checkbox.toggled.connect(self.on_column_mapping_toggled)

    
    def show_info_dialog(self):
        """Показать диалог с описанием интерфейса"""
        Logger.log_message("Отображение справочной информации")
        dialog = InfoDialog(self.lm.get_string("EXPORT_DIALOG", "help_dialog_title"), 
                           self.lm.get_string("HELP_CONTENT", "EXPORT_DIALOG"), self)
        dialog.exec_()

    def load_last_connection(self):
        """Загрузка последнего использованного подключения к базе данных из настроек QGIS"""
        Logger.log_message("Загрузка последнего подключения к БД")
        settings = QgsSettings()
        self.address = settings.value("DXFPostGIS/lastConnection/host", 'none')
        self.port = settings.value("DXFPostGIS/lastConnection/port", '5432')
        self.dbname = settings.value("DXFPostGIS/lastConnection/database", 'none')
        self.username = settings.value("DXFPostGIS/lastConnection/username", 'none')
        self.password = settings.value("DXFPostGIS/lastConnection/password", 'none')
        self.schemaname = settings.value("DXFPostGIS/lastConnection/schema", 'none')        
        # Загружаем настройки схем и режима экспорта
        self.layer_schema = settings.value("DXFPostGIS/lastConnection/layerSchema", 'layer_schema')
        self.file_schema = settings.value("DXFPostGIS/lastConnection/fileSchema", 'file_schema')
        self.export_layers_only = settings.value("DXFPostGIS/lastConnection/exportLayersOnly", False, type=bool)
        
        # Загружаем пользовательское название файла
        self.custom_filename = settings.value("DXFPostGIS/lastConnection/customFilename", "")
        self.filename_lineedit.setText(self.custom_filename)
        
        # Устанавливаем состояние чекбокса
        self.export_layers_only_checkbox.setChecked(self.export_layers_only)

        if self.dbname != 'none':
            Logger.log_message(f"Загружены параметры БД: {self.dbname} на {self.address}")
            self.refresh_data_dialog()
        else:
            Logger.log_message("Подключение к БД не настроено, загружаем схемы по умолчанию")
            # Если нет подключения к БД, устанавливаем схемы по умолчанию
            self.setup_default_schemas()

    def setup_default_schemas(self):
        """Настройка схем по умолчанию когда нет подключения к БД"""
        Logger.log_message("Настройка схем по умолчанию")
        # Очищаем комбобоксы
        self.layer_schema_combo.clear()
        self.file_schema_combo.clear()
        
        # Добавляем схемы по умолчанию
        default_schemas = ['layer_schema', 'file_schema', 'public']
        for schema in default_schemas:
            self.layer_schema_combo.addItem(schema)
            self.file_schema_combo.addItem(schema)
        
        # Устанавливаем сохраненные значения или значения по умолчанию
        layer_index = self.layer_schema_combo.findText(self.layer_schema)
        if layer_index >= 0:
            self.layer_schema_combo.setCurrentIndex(layer_index)
        else:
            self.layer_schema_combo.setCurrentIndex(0)
            
        file_index = self.file_schema_combo.findText(self.file_schema)
        if file_index >= 0:
            self.file_schema_combo.setCurrentIndex(file_index)
        else:
            self.file_schema_combo.setCurrentIndex(1)  # file_schema
        
        # Проверяем возможность экспорта
        self.check_export_enabled()

    def save_current_connection(self):
        """Сохранение текущего подключения к базе данных в настройках QGIS"""
        Logger.log_message("Сохранение параметров текущего подключения")
        settings = QgsSettings()
        settings.setValue("DXFPostGIS/lastConnection/host", self.address)
        settings.setValue("DXFPostGIS/lastConnection/port", self.port)
        settings.setValue("DXFPostGIS/lastConnection/database", self.dbname)
        settings.setValue("DXFPostGIS/lastConnection/username", self.username)
        settings.setValue("DXFPostGIS/lastConnection/password", self.password)
        settings.setValue("DXFPostGIS/lastConnection/schema", self.schemaname)
          # Сохраняем настройки схем
        settings.setValue("DXFPostGIS/lastConnection/layerSchema", self.layer_schema)
        settings.setValue("DXFPostGIS/lastConnection/fileSchema", self.file_schema)
        settings.setValue("DXFPostGIS/lastConnection/exportLayersOnly", self.export_layers_only)
          # Сохраняем пользовательское название файла
        settings.setValue("DXFPostGIS/lastConnection/customFilename", self.custom_filename)

    def on_port_changed(self, text):
        """
        Обработка изменения порта.
        
        :param text: Новое значение порта
        """
        self.port = text
        Logger.log_message(f"Изменен порт: {text}")

    def on_password_changed(self, text):
        """
        Обработка изменения пароля.
        
        :param text: Новое значение пароля
        """
        self.password = text
        Logger.log_message("Пароль был изменен")
        self.check_export_enabled()

    def on_filename_changed(self, text):
        """
        Обработка изменения названия файла.
        
        :param text: Новое название файла
        """
        self.custom_filename = text.strip()
        Logger.log_message(f"Название файла изменено на: '{self.custom_filename}'")
        self.check_export_enabled()


    def refresh_data_dialog(self):
        """Обновление данных диалога на основе текущих настроек подключения"""
        Logger.log_message("Обновление данных диалога экспорта")
        self.address_label.setText(self.address)
        self.port_lineedit.setText(self.port)
        self.dbname_label.setText(self.dbname)
        self.schema_label.setText(self.schemaname)
        self.username_label.setText(self.username)
        self.password_lineedit.setText(self.password)

        # Загружаем схемы из базы данных
        self.load_schemas()

        # Показываем окно
        self.show_window()
        
        # Проверяем возможность экспорта
        self.check_export_enabled()

    def show_window(self):
        """Отображение диалогового окна и перевод его в активное состояние"""
        Logger.log_message("Отображение диалогового окна экспорта")
        # Показать окно и сделать его активным
        self.raise_()
        self.activateWindow()
        self.show()

    def on_select_db_button_clicked(self):
        """Обработка нажатия кнопки выбора базы данных"""
        Logger.log_message("Открытие диалога выбора базы данных")
        from .providers_dialog import ProvidersDialog
        
        if self.dlg is None:
            self.dlg = ProvidersDialog()
            self.dlg.show()
            result = self.dlg.exec_()

            if result and self.dlg.db_tree.currentSchema() is not None:
                Logger.log_message("База данных успешно выбрана")
                self.address = self.dlg.db_tree.currentDatabase().connection().db.connector.host
                self.port = self.dlg.db_tree.currentDatabase().connection().db.connector.port
                self.dbname = self.dlg.db_tree.currentDatabase().connection().db.connector.dbname
                self.username = self.dlg.db_tree.currentDatabase().connection().db.connector.user

                # Получаем учетные данные через универсальный метод ConnectionsManager
                username, password = self.connection_manager.get_credentials(
                    self.address, 
                    self.port, 
                    self.dbname,
                    default_username=self.username,
                    parent=self
                )
                
                if username and password:
                    self.username = username
                    self.password = password
                    self.schemaname = self.dlg.db_tree.currentSchema().name
                    self.save_current_connection()
                    
                    self.refresh_data_dialog()
                else:
                    Logger.log_error("Не удалось получить учетные данные для доступа к БД")
                    
                self.dlg = None
            else:                Logger.log_message("Выбор базы данных отменен пользователем")

    def check_export_enabled(self):
        """Проверяет, можно ли включить кнопку экспорта"""
        # Основные требования
        basic_requirements = (
            self.dbname != 'none' and 
            self.username != 'none'
        )
          # Проверка схем
        layer_schema_selected = (
            hasattr(self, 'layer_schema_combo') and 
            self.layer_schema_combo.currentText() != "" and
            self.layer_schema_combo.currentText() != "none"
        )
        
        # Если экспортируем только слои, схема файлов не нужна
        if self.export_layers_only:
            schema_requirements = layer_schema_selected
        else:
            # Если экспортируем файлы тоже, нужны обе схемы
            file_schema_selected = (
                hasattr(self, 'file_schema_combo') and
                self.file_schema_combo.currentText() != "" and
                self.file_schema_combo.currentText() != "none"
            )
            schema_requirements = layer_schema_selected and file_schema_selected
        
        can_export = basic_requirements and (schema_requirements or (self.layer_schema is not None and self.file_schema is not None))
        
        self.export_button.setEnabled(can_export)
          # Логирование для отладки
        if not can_export:
            if not basic_requirements:
                Logger.log_message("Экспорт недоступен: не настроено подключение к БД")
            elif not schema_requirements:
                Logger.log_message("Экспорт недоступен: не выбраны необходимые схемы")

    def on_cancel_clicked(self):
        """Обработка нажатия кнопки Отмена"""
        Logger.log_message("Экспорт отменен пользователем")
        if hasattr(self, 'display_tree_handler'):
            self.display_tree_handler.cleanup()
        self.reject()

    def on_export_clicked(self):
        """Обработка нажатия кнопки Экспорт"""
        
        # Сохраняем текущие настройки подключения и схем перед экспортом
        self.save_current_connection()
            
        # Создаем и настраиваем диалог прогресса
        self.progress = QProgressDialog(self.lm.get_string("EXPORT_DIALOG", "export_progress"), None, 0, 0, self)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setWindowTitle(self.lm.get_string("EXPORT_DIALOG", "export_title"))
        self.progress.setAutoClose(True)
        self.progress.setCancelButton(None)
        self.progress.setMinimumDuration(0)
        
        # Настраиваем размеры и позиционирование
        self.progress.setFixedWidth(400)  # Фиксированная ширина
        self.progress.setMinimumHeight(120)  # Минимальная высота
        
        # Получаем лейбл для настройки переноса текста
        progress_label = self.progress.findChild(QLabel)
        if progress_label:
            progress_label.setWordWrap(True)  # Включаем перенос слов
            progress_label.setMaximumWidth(370)  # Ограничиваем ширину текста
        
        
        # Добавляем анимацию точек
        self.dots = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress_text)
        self.timer.start(500)
        
        # Получаем выбранный режим маппирования
        mapping_mode = self.mapping_mode_combo.currentData()
        Logger.log_message(f"Выбран режим маппирования для экспорта: {mapping_mode}")
          # Создаем временный файл для экспорта
        selected_file_name = self.dxf_tree_widget_handler.get_selected_file_name()
        if not selected_file_name:
            Logger.log_error("Не удалось определить имя выбранного файла")
            self.timer.stop()
            self.progress.close()
            return
          # Используем пользовательское название файла, если оно задано
        final_filename = self.custom_filename if self.custom_filename else selected_file_name
        
        # Убеждаемся, что файл имеет расширение .dxf
        if final_filename and not final_filename.lower().endswith('.dxf'):
            final_filename += '.dxf'
            
        Logger.log_message(f"Название файла для экспорта: '{final_filename}' (оригинальное: '{selected_file_name}')")
            
        # Создаем экспортер DXF
        dxf_exporter = DXFExporter(self.dxf_handler)
        
        # Создаем временный файл
        temp_dir = tempfile.gettempdir()
        temp_filename = os.path.join(temp_dir, final_filename)
        
        self.update_progress(10, self.lm.get_string("EXPORT_DIALOG", "creating_temp_file"))
        
        # Экспортируем выбранные сущности во временный файл
        # Используем оригинальное название файла для получения сущностей
        export_success = dxf_exporter.export_selected_entities(selected_file_name, temp_filename)
        
        if not export_success:
            Logger.log_error("Не удалось создать временный DXF файл для экспорта")
            QtWidgets.QMessageBox.critical(
                self,
                self.lm.get_string("EXPORT_DIALOG", "error_title"),
                self.lm.get_string("EXPORT_DIALOG", "temp_file_error")
            )
            self.timer.stop()
            self.progress.close()
            return
            
        self.update_progress(20, self.lm.get_string("EXPORT_DIALOG", "temp_file_created"))
        Logger.log_message(f"Создан временный файл для экспорта: {temp_filename}")
          # Получаем выбранные схемы
        layer_schema = self.layer_schema_combo.currentText()
        file_schema = self.file_schema_combo.currentText() if not self.export_layers_only else 'file_schema'
        
        Logger.log_message(f"Схема для слоев: {layer_schema}")
        Logger.log_message(f"Схема для файлов: {file_schema}")
        Logger.log_message(f"Экспорт только слоев: {self.export_layers_only}")
          # Создаем и запускаем поток экспорта с временным файлом
        self.export_thread = ExportThread(
            self.username,
            self.password,
            self.address,
            self.port,
            self.dbname,
            self.dxf_handler,
            temp_filename,
            mapping_mode,
            layer_schema,
            file_schema,
            self.export_layers_only,
            final_filename,  # Передаем пользовательское название файла
            self.column_mapping_configs if self.enable_column_mapping_checkbox.isChecked() else {}
        )
        
        # Сохраняем имя временного файла для удаления после завершения экспорта
        self.temp_filename = temp_filename
        
        self.export_thread.progress_update.connect(self.update_progress)
        self.export_thread.finished.connect(self.on_export_finished)
        self.export_thread.start()
        
        # Показываем прогресс
        self.progress.show()

    def update_progress(self, percent, message):
        """
        Обновляет прогресс-бар и сообщение
        
        :param percent: Процент выполнения (0-100)
        :param message: Сообщение о текущем этапе
        """
        if self.progress:
            self.progress.setLabelText(message)
            if percent > 0:  # Если передан конкретный процент
                self.progress.setMaximum(100)
                self.progress.setValue(percent)
            else:  # Если процент не определен, показываем бесконечный прогресс
                self.progress.setMaximum(0)

    def update_progress_text(self):
        """Обновление текста в окне прогресса (анимация точек)"""
        if self.progress:
            self.dots = (self.dots + 1) % 4
            # Получаем базовый текст без точек
            base_text = self.progress.labelText().rstrip('.')
            # Добавляем нужное количество точек
            animated_text = base_text + '.' * self.dots
            self.progress.setLabelText(animated_text)

    def on_export_finished(self, success, message):
        """Обработка завершения экспорта"""
        self.timer.stop()
        if hasattr(self, 'progress') and self.progress:
            self.progress.close()
        
        # Удаляем временный файл после завершения экспорта
        if hasattr(self, 'temp_filename') and self.temp_filename:
            try:
                if os.path.exists(self.temp_filename):
                    os.remove(self.temp_filename)
                    Logger.log_message(f"Временный файл удален: {self.temp_filename}")
            except Exception as e:
                Logger.log_error(f"Ошибка при удалении временного файла: {str(e)}")
        
        if success:
            QtWidgets.QMessageBox.information(self, 
                                             self.lm.get_string("EXPORT_DIALOG", "success_title"), 
                                             message)
            self.accept()
        else:
            Logger.log_error(f"Ошибка при экспорте: {message}")
            QtWidgets.QMessageBox.critical(
                self,
                self.lm.get_string("EXPORT_DIALOG", "error_title"),
                self.lm.get_string("EXPORT_DIALOG", "export_error", message)
            )

    def update_mapping_description(self, index):
        """
        Обновляет описание режима маппирования в зависимости от выбранного индекса.
        
        :param index: Индекс выбранного элемента в комбобоксе
        """
        mapping_mode = self.mapping_mode_combo.currentData()
        description = ""
        
        if mapping_mode == "always_overwrite":
            description = self.lm.get_string("EXPORT_DIALOG", "desc_always_overwrite", 
                          "Все существующие объекты в базе данных будут заменены новыми. Используйте этот режим, когда хотите полностью обновить слои.")        
        elif mapping_mode == "geometry":
            description = self.lm.get_string("EXPORT_DIALOG", "desc_geometry", 
                          "Объекты с одинаковой геометрией будут обновлены, уникальные объекты будут добавлены. Удобно для сохранения иерархии объектов.")
        elif mapping_mode == "notes":
            description = self.lm.get_string("EXPORT_DIALOG", "desc_notes", 
                          "Объекты с одинаковыми примечаниями будут обновлены. Удобно, когда примечания используются как уникальные идентификаторы.")
        elif mapping_mode == "both":
            description = self.lm.get_string("EXPORT_DIALOG", "desc_both", 
                          "Сравнение будет производиться как по геометрии, так и по примечаниям. Наиболее строгий вариант сопоставления.")
        
        self.mapping_description.setText(description)
        Logger.log_message(f"Выбран режим маппирования: {mapping_mode}")

    def load_schemas(self):
        """Загружает список доступных схем из базы данных"""
        try:
            # Проверяем, есть ли параметры подключения
            if self.dbname == 'none' or self.username == 'none':
                Logger.log_message("Параметры подключения к БД не настроены")
                return
                
            self.available_schemas = get_schemas(self.username, self.password, self.address, self.port, self.dbname)
            Logger.log_message(f"Загружено схем: {len(self.available_schemas)}")
            
            # Если схемы не загрузились (пустой список), не обновляем комбобоксы
            if not self.available_schemas:
                Logger.log_message("Схемы не загрузились - комбобоксы остаются без изменений")
                return
            
            # Сохраняем текущие выборы
            current_layer_schema = self.layer_schema_combo.currentText()
            current_file_schema = self.file_schema_combo.currentText()
            
            # Очищаем комбобоксы
            self.layer_schema_combo.clear()
            self.file_schema_combo.clear()
            
            # Добавляем схемы в комбобоксы
            for schema in self.available_schemas:
                self.layer_schema_combo.addItem(schema)
                self.file_schema_combo.addItem(schema)
            
            # Восстанавливаем предыдущие выборы или устанавливаем значения по умолчанию
            layer_index = self.layer_schema_combo.findText(current_layer_schema or self.layer_schema)
            if layer_index >= 0:
                self.layer_schema_combo.setCurrentIndex(layer_index)
            elif self.available_schemas:
                # Если схема по умолчанию не найдена, выбираем первую доступную
                self.layer_schema_combo.setCurrentIndex(0)
                self.layer_schema = self.layer_schema_combo.currentText()
            
            file_index = self.file_schema_combo.findText(current_file_schema or self.file_schema)
            if file_index >= 0:
                self.file_schema_combo.setCurrentIndex(file_index)
            elif self.available_schemas:
                # Если схема по умолчанию не найдена, выбираем первую доступную
                self.file_schema_combo.setCurrentIndex(0)
                self.file_schema = self.file_schema_combo.currentText()
                
        except Exception as e:
            Logger.log_error(f"Ошибка при загрузке схем: {str(e)}")
            # При ошибке просто логируем, но не добавляем схемы по умолчанию
            # Пользователь может попробовать снова открыть список или исправить подключение
        
        # Проверяем возможность экспорта после загрузки схем
        self.check_export_enabled()

    def on_layer_schema_popup(self):
        """Обработка открытия выпадающего списка схем для слоев - повторная загрузка схем"""
        Logger.log_message("Открытие списка схем для слоев - проверяем наличие новых схем")
        
        # Если список пуст или есть подключение к БД, пытаемся перезагрузить схемы
        if self.layer_schema_combo.count() == 0 or self.dbname != 'none':
            current_selection = self.layer_schema_combo.currentText()
            self.load_schemas()
            
            # Восстанавливаем выбор если он был
            if current_selection:
                index = self.layer_schema_combo.findText(current_selection)
                if index >= 0:
                    self.layer_schema_combo.setCurrentIndex(index)
        
        # Вызываем стандартный showPopup
        QComboBox.showPopup(self.layer_schema_combo)

    def on_file_schema_popup(self):
        """Обработка открытия выпадающего списка схем для файлов - повторная загрузка схем"""
        Logger.log_message("Открытие списка схем для файлов - проверяем наличие новых схем")
        
        # Если список пуст или есть подключение к БД, пытаемся перезагрузить схемы
        if self.file_schema_combo.count() == 0 or self.dbname != 'none':
            current_selection = self.file_schema_combo.currentText()
            self.load_schemas()
            
            # Восстанавливаем выбор если он был
            if current_selection:
                index = self.file_schema_combo.findText(current_selection)
                if index >= 0:
                    self.file_schema_combo.setCurrentIndex(index)
        
        # Вызываем стандартный showPopup
        QComboBox.showPopup(self.file_schema_combo)

    def on_layer_schema_changed(self, schema_name):
        """Обработка изменения схемы для слоев"""
        self.layer_schema = schema_name
        Logger.log_message(f"Выбрана схема для слоев: {schema_name}")
        self.check_export_enabled()

    def on_file_schema_changed(self, schema_name):
        """Обработка изменения схемы для файлов"""
        self.file_schema = schema_name
        Logger.log_message(f"Выбрана схема для файлов: {schema_name}")
        self.check_export_enabled()

    def on_export_layers_only_toggled(self, checked):
        """Обработка изменения чекбокса 'Экспортировать только слои'"""
        self.export_layers_only = checked
        # Отключаем/включаем элементы схемы файлов
        self.file_schema_combo.setEnabled(not checked)
        self.create_file_schema_button.setEnabled(not checked)
        Logger.log_message(f"Экспорт только слоев: {checked}")
        self.check_export_enabled()

    def show_layer_schema_creation(self):
        """Показывает поля для создания новой схемы слоев"""
        self.layer_schema_name_widget.setVisible(True)
        self.layer_schema_name_input.clear()
        self.layer_schema_name_input.setFocus()

    def hide_layer_schema_creation(self):
        """Скрывает поля для создания новой схемы слоев"""
        self.layer_schema_name_widget.setVisible(False)
        self.layer_schema_name_input.clear()

    def show_file_schema_creation(self):
        """Показывает поля для создания новой схемы файлов"""
        self.file_schema_name_widget.setVisible(True)
        self.file_schema_name_input.clear()
        self.file_schema_name_input.setFocus()

    def hide_file_schema_creation(self):
        """Скрывает поля для создания новой схемы файлов"""
        self.file_schema_name_widget.setVisible(False)
        self.file_schema_name_input.clear()

    def validate_schema_name(self, schema_name):
        """
        Валидация имени схемы
        
        :param schema_name: Имя схемы для проверки
        :return: True если имя валидно, иначе False
        """
        if not schema_name:
            return False
        
        # Проверка на валидные символы (только буквы, цифры, подчеркивания)
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', schema_name):
            return False
        
        # Проверка длины
        if len(schema_name) > 63:  # PostgreSQL limit
            return False
            
        return True

    def create_layer_schema(self):
        """Создает новую схему для слоев"""
        schema_name = self.layer_schema_name_input.text().strip()
        
        if not self.validate_schema_name(schema_name):
            QMessageBox.warning(self, 
                              self.lm.get_string("EXPORT_DIALOG", "warning_title"),
                              self.lm.get_string("EXPORT_DIALOG", "invalid_schema_name"))
            return
            
        try:
            if create_schema(self.username, self.password, self.address, self.port, self.dbname, schema_name):
                # Обновляем список схем
                self.load_schemas()
                
                # Выбираем созданную схему
                index = self.layer_schema_combo.findText(schema_name)
                if index >= 0:
                    self.layer_schema_combo.setCurrentIndex(index)
                
                self.hide_layer_schema_creation()
                Logger.log_message(f"Создана схема для слоев: {schema_name}")
            else:
                QMessageBox.critical(self,
                                   self.lm.get_string("EXPORT_DIALOG", "error_title"),
                                   self.lm.get_string("EXPORT_DIALOG", "schema_creation_failed"))
        except Exception as e:
            Logger.log_error(f"Ошибка при создании схемы: {str(e)}")
            QMessageBox.critical(self,
                               self.lm.get_string("EXPORT_DIALOG", "error_title"),
                               f"{self.lm.get_string('EXPORT_DIALOG', 'schema_creation_failed')}: {str(e)}")

    def create_file_schema(self):
        """Создает новую схему для файлов"""
        schema_name = self.file_schema_name_input.text().strip()
        if not self.validate_schema_name(schema_name):
            QMessageBox.warning(self, 
                              self.lm.get_string("EXPORT_DIALOG", "warning_title"),
                              self.lm.get_string("EXPORT_DIALOG", "invalid_schema_name"))
            return
            
        try:
            if create_schema(self.username, self.password, self.address, self.port, self.dbname, schema_name):
                # Обновляем список схем
                self.load_schemas()
                
                # Выбираем созданную схему
                index = self.file_schema_combo.findText(schema_name)
                if index >= 0:
                    self.file_schema_combo.setCurrentIndex(index)
                
                self.hide_file_schema_creation()
                Logger.log_message(f"Создана схема для файлов: {schema_name}")
            else:
                QMessageBox.critical(self,
                                   self.lm.get_string("EXPORT_DIALOG", "error_title"),
                                   self.lm.get_string("EXPORT_DIALOG", "schema_creation_failed"))
        except Exception as e:
            Logger.log_error(f"Ошибка при создании схемы: {str(e)}")
            QMessageBox.critical(self,
                               self.lm.get_string("EXPORT_DIALOG", "error_title"),
                               f"{self.lm.get_string('EXPORT_DIALOG', 'schema_creation_failed')}: {str(e)}")

    def on_column_mapping_toggled(self, checked):
        """Обработка включения/выключения сопоставления столбцов"""
        self.configure_mapping_button.setEnabled(checked)
        if checked:
            Logger.log_message("Включено сопоставление столбцов")
        else:
            Logger.log_message("Выключено сопоставление столбцов")
            # Очищаем настройки сопоставления
            self.column_mapping_configs = {}    
    def configure_column_mapping(self):
        """Открытие диалога настройки сопоставления столбцов"""
        if not self.enable_column_mapping_checkbox.isChecked():
            return
            
        Logger.log_message("Открытие диалога настройки сопоставления столбцов")
        
        # Проверяем подключение к БД
        if self.dbname == 'none' or self.username == 'none':
            QtWidgets.QMessageBox.warning(
                self, 
                "Предупреждение",
                "Для настройки сопоставления столбцов необходимо выбрать базу данных"
            )
            return
        
        # Создаем диалог сопоставления столбцов
        db_connection_params = {
            'username': self.username,
            'password': self.password,
            'address': self.address,
            'port': self.port,
            'dbname': self.dbname
        }
        
        # Импортируем диалог сопоставления столбцов
        from .column_mapping_dialog import ColumnMappingDialog
        
        dialog = ColumnMappingDialog(
            db_connection_params=db_connection_params,
            layer_schema=self.layer_schema,
            parent=self
        )        
        # Подключаем сигнал для получения результата
        dialog.mapping_configured.connect(self.on_mapping_configured)
        
        # Показываем диалог
        dialog.exec_()
    
    def open_mapping_dialog_for_layer(self, layer_name):
        """Открыть диалог сопоставления для конкретного слоя"""
        from .column_mapping_dialog import ColumnMappingDialog
        from ..db.database import table_exists
        
        # Проверяем существование таблицы
        table_name = layer_name.replace(' ', '_').replace('-', '_')
        layer_schema = self.layer_schema_combo.currentText()
        
        exists = table_exists(
            self.username, self.password, self.address, 
            self.port, self.dbname, table_name, layer_schema
        )
        
        if not exists:
            QtWidgets.QMessageBox.information(
                self,
                "Информация",
                f"Таблица для слоя '{layer_name}' не существует в БД.\n"
                f"Сопоставление столбцов доступно только для существующих таблиц."
            )
            return
        
        # Получаем столбцы DXF для данного слоя
        dxf_columns = self.get_dxf_columns_for_layer(layer_name)
        
        if not dxf_columns:
            QtWidgets.QMessageBox.warning(
                self,
                "Предупреждение", 
                f"Не удалось определить столбцы для слоя '{layer_name}'"
            )
            return
        
        # Параметры подключения к БД
        db_params = {
            'username': self.username,
            'password': self.password,
            'address': self.address,
            'port': self.port,
            'dbname': self.dbname
        }
        
        # Создаем диалог сопоставления
        mapping_dialog = ColumnMappingDialog(
            layer_name, dxf_columns, db_params, layer_schema, self
        )
        mapping_dialog.mapping_configured.connect(self.on_mapping_configured)
        mapping_dialog.exec_()
    
    def get_dxf_columns_for_layer(self, layer_name):
        """Получение столбцов DXF для слоя (базовые столбцы таблицы слоя)"""
        # Базовые столбцы, которые всегда есть в таблице слоя
        base_columns = {
            'id': 'INTEGER',
            'geometry': 'GEOMETRY',
            'geom_type': 'VARCHAR',
            'layer_name': 'VARCHAR',
            'color': 'INTEGER',
            'linetype': 'VARCHAR',
            'lineweight': 'VARCHAR',
            'ltscale': 'DOUBLE PRECISION',
            'invisible': 'BOOLEAN',
            'true_color': 'INTEGER',
            'transparency': 'INTEGER',
            'notes': 'TEXT',
            'extra_data': 'JSONB',
            'file_id': 'INTEGER'
        }
        
        # Здесь можно добавить логику для получения дополнительных столбцов
        # на основе конкретных сущностей в слое
        
        return base_columns    
    def on_mapping_configured(self, mapping_config):
        """Обработчик настройки сопоставления столбцов"""
        Logger.log_message(f"Получена конфигурация сопоставления: {mapping_config}")
        
        # Сохраняем глобальную конфигурацию сопоставления
        if not hasattr(self, 'column_mapping_configs'):
            self.column_mapping_configs = {}
        
        # Сохраняем конфигурацию как общий паттерн для всех слоев
        self.column_mapping_configs['global_pattern'] = mapping_config        
        Logger.log_message("Настройки сопоставления столбцов сохранены как глобальный паттерн")
        
        QtWidgets.QMessageBox.information(
            self,
            "Успех",
            "Сопоставление столбцов настроено успешно как глобальный паттерн"
        )
