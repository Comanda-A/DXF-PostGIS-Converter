from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                           QTreeWidget, QLabel, QPushButton, QLineEdit, QWidget, 
                           QComboBox, QTreeWidgetItem, QProgressDialog)
from qgis.core import QgsSettings

from ..localization.localization_manager import LocalizationManager

from ..db.connections_manager import ConnectionsManager
from ..tree_widget_handler import TreeWidgetHandler
from ..logger.logger import Logger
from ..dxf.dxf_handler import DXFHandler
from ..dxf.dxf_exporter import DXFExporter
from ..db.database import (export_dxf_to_database, get_all_layers_for_file, get_layer_entities, get_all_dxf_files)
from .info_dialog import InfoDialog
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QThread, pyqtSignal
import os
import tempfile

# маппирование для сравнения геометрии и примечаний (notes), всегда с перезаписью файла

class ExportThread(QThread):
    """
    Поток для выполнения экспорта данных в базу данных.
    Работает отдельно от основного потока интерфейса, чтобы не блокировать UI.
    """
    finished = pyqtSignal(bool, str)  # Сигнал: успех/неуспех, сообщение
    progress_update = pyqtSignal(int, str)  # Сигнал обновления прогресса: процент, сообщение
    
    def __init__(self, username, password, address, port, dbname, dxf_handler, file_path, mapping_mode):
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
        self.lm = LocalizationManager.instance()

    def run(self):
        """
        Основной метод потока. Выполняет экспорт и отправляет сигнал о результате.
        """
        try:
            Logger.log_message(self.lm.get_string("EXPORT_DIALOG", "export_thread_start"))
            Logger.log_message(f"Режим маппирования: {self.mapping_mode}")
            
            self.progress_update.emit(0, self.lm.get_string("EXPORT_DIALOG", "progress_text"))
            
            result = export_dxf_to_database(
                self.username,
                self.password,
                self.address,
                self.port,
                self.dbname,
                self.dxf_handler,
                self.file_path,
                self.mapping_mode
            )
            
            if result:
                Logger.log_message(self.lm.get_string("EXPORT_DIALOG", "export_thread_success"))
                self.finished.emit(True, self.lm.get_string("EXPORT_DIALOG", "export_thread_complete"))
            else:
                Logger.log_error("Экспорт не был завершен успешно")
                self.finished.emit(False, self.lm.get_string("EXPORT_DIALOG", "export_thread_failed"))
        except Exception as e:
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

    def _connect_signals(self):
        """Подключение всех сигналов пользовательского интерфейса"""
        Logger.log_message("Подключение сигналов интерфейса")
        self.select_db_button.clicked.connect(self.on_select_db_button_clicked)
        self.info_button.clicked.connect(self.show_info_dialog)
        self.port_lineedit.textChanged.connect(self.on_port_changed)
        self.password_lineedit.textChanged.connect(self.on_password_changed)
        self.export_button.clicked.connect(self.on_export_clicked)
        self.cancel_button.clicked.connect(self.on_cancel_clicked)
        # Подключаем сигнал изменения режима маппирования
        self.mapping_mode_combo.currentIndexChanged.connect(self.update_mapping_description)

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

        if self.dbname != 'none':
            Logger.log_message(f"Загружены параметры БД: {self.dbname} на {self.address}")
            self.refresh_data_dialog()

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


    def refresh_data_dialog(self):
        """Обновление данных диалога на основе текущих настроек подключения"""
        Logger.log_message("Обновление данных диалога экспорта")
        self.address_label.setText(self.address)
        self.port_lineedit.setText(self.port)
        self.dbname_label.setText(self.dbname)
        self.schema_label.setText(self.schemaname)
        self.username_label.setText(self.username)
        self.password_lineedit.setText(self.password)

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
            else:
                Logger.log_message("Выбор базы данных отменен пользователем")

    def check_export_enabled(self):
        """Проверяет, можно ли включить кнопку экспорта"""
        can_export = (
            self.dbname != 'none' and 
            self.username != 'none'
        )
        
        self.export_button.setEnabled(can_export)

    def on_cancel_clicked(self):
        """Обработка нажатия кнопки Отмена"""
        Logger.log_message("Экспорт отменен пользователем")
        if hasattr(self, 'display_tree_handler'):
            self.display_tree_handler.cleanup()
        self.reject()

    def on_export_clicked(self):
        """Обработка нажатия кнопки Экспорт"""
            
        # Создаем и настраиваем диалог прогресса
        self.progress = QProgressDialog(self.lm.get_string("EXPORT_DIALOG", "export_progress"), None, 0, 0, self)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setWindowTitle(self.lm.get_string("EXPORT_DIALOG", "export_title"))
        self.progress.setAutoClose(True)
        self.progress.setCancelButton(None)
        self.progress.setMinimumDuration(0)
        
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
            
        # Создаем экспортер DXF
        dxf_exporter = DXFExporter(self.dxf_handler)
        
        # Создаем временный файл
        temp_dir = tempfile.gettempdir()
        temp_filename = os.path.join(temp_dir, selected_file_name)
        
        self.update_progress(10, self.lm.get_string("EXPORT_DIALOG", "creating_temp_file"))
        
        # Экспортируем выбранные сущности во временный файл
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
        
        # Создаем и запускаем поток экспорта с временным файлом
        self.export_thread = ExportThread(
            self.username,
            self.password,
            self.address,
            self.port,
            self.dbname,
            self.dxf_handler,
            temp_filename,
            mapping_mode
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
