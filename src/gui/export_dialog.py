from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                           QTreeWidget, QLabel, QPushButton, QLineEdit, QWidget, 
                           QComboBox, QTabWidget, QTableWidget, QDialogButtonBox,
                           QHeaderView, QTreeWidgetItem, QProgressDialog)
from qgis.core import QgsSettings

from ..localization.localization_manager import LocalizationManager

from ..db.connections_manager import ConnectionsManager
from ..tree_widget_handler import TreeWidgetHandler
from ..logger.logger import Logger
from ..dxf.dxf_handler import DXFHandler
from ..db.database import export_dxf
from ..db.database import (get_layer_objects, get_layers_for_file)
from .info_dialog import InfoDialog
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QThread, pyqtSignal

class ExportThread(QThread):
    """
    Поток для выполнения экспорта данных в базу данных.
    Работает отдельно от основного потока интерфейса, чтобы не блокировать UI.
    """
    finished = pyqtSignal(bool, str)  # Сигнал: успех/неуспех, сообщение
    
    def __init__(self, username, password, address, port, dbname, dxf_handler, table_info):
        """
        Инициализация потока экспорта.
        
        :param username: Имя пользователя для подключения к БД
        :param password: Пароль пользователя
        :param address: Адрес сервера БД
        :param port: Порт сервера БД
        :param dbname: Имя базы данных
        :param dxf_handler: Обработчик DXF-файлов
        :param table_info: Информация о таблице для экспорта
        """
        super().__init__()
        self.username = username
        self.password = password
        self.address = address
        self.port = port
        self.dbname = dbname
        self.dxf_handler = dxf_handler
        self.table_info = table_info
        self.lm = LocalizationManager.instance()

    def run(self):
        """
        Основной метод потока. Выполняет экспорт и отправляет сигнал о результате.
        """
        try:
            Logger.log_message(self.lm.get_string("EXPORT_DIALOG", "export_thread_start"))
            export_dxf(
                self.username,
                self.password,
                self.address,
                self.port,
                self.dbname,
                self.dxf_handler,
                self.table_info
            )
            Logger.log_message(self.lm.get_string("EXPORT_DIALOG", "export_thread_success"))
            self.finished.emit(True, self.lm.get_string("EXPORT_DIALOG", "export_thread_complete"))
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
        self.selected_file_id = None
        self.is_new_file = True
        self.selected_file_name = None
        self.selected_layer_id = None
        self.geom_mappings = {}  # Сопоставления геометрических объектов
        self.nongeom_mappings = {}  # Сопоставления негеометрических объектов
        self.import_mode = 'overwrite'  # Режим импорта по умолчанию - "Перезапись"
        self.dlg = None
        self.connection_manager = ConnectionsManager()

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

    def setup_ui(self):
        """Создание и настройка элементов пользовательского интерфейса"""
        Logger.log_message("Настройка интерфейса диалога экспорта")
        
        self.setWindowTitle(self.lm.get_string("EXPORT_DIALOG", "title"))
        self.setMinimumWidth(1200)
        self.setMinimumHeight(800)

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

        # Контент панели может быть растянут 
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # Левая колонка – для DXF объектов и подключения к базе данных
        left_column = QVBoxLayout()
        left_column.setSpacing(10)
        
        # Группа DXF объектов - use localized group title
        self.dxf_group = QGroupBox(self.lm.get_string("EXPORT_DIALOG", "dxf_objects_group"))
        dxf_layout = QVBoxLayout()
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setColumnCount(1)  # Одна колонка для отображения объектов
        self.tree_widget.setMinimumHeight(300)
        self.tree_widget.setMinimumWidth(400)
        dxf_layout.addWidget(self.tree_widget)
        self.dxf_group.setLayout(dxf_layout)
        left_column.addWidget(self.dxf_group)

        # Группа подключения к базе данных - use localized group title
        self.connection_group = QGroupBox(self.lm.get_string("EXPORT_DIALOG", "db_connection_group"))
        conn_layout = QVBoxLayout()
        
        # Строка адреса - use localized labels
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

        # Правая колонка – для выбора файла и сопоставления
        right_column = QVBoxLayout()
        right_column.setSpacing(10)
        
        # Контейнер для правой колонки с фиксированной шириной
        right_widget = QWidget()
        right_widget.setMaximumWidth(600)  # Фиксированная максимальная ширина
        right_widget.setMinimumWidth(500)  # Минимальная ширина
        right_widget.setLayout(right_column)
        
        # Группа выбора файла
        self.file_group = QGroupBox(self.lm.get_string("EXPORT_DIALOG", "file_selection_group"))
        file_layout = QVBoxLayout()
        
        # Выбор существующего файла и ввод имени
        self.file_combo = QComboBox()
        self.new_file_name = QLineEdit()
        self.new_file_name.setPlaceholderText(self.lm.get_string("EXPORT_DIALOG", "new_file_placeholder"))
        
        # Выбор режима импорта
        self.import_mode_group = QGroupBox(self.lm.get_string("EXPORT_DIALOG", "import_mode_group"))
        self.import_mode_group.setVisible(False)  # Изначально скрыт
        mode_layout = QVBoxLayout()
        
        self.mapping_radio = QtWidgets.QRadioButton(self.lm.get_string("EXPORT_DIALOG", "mapping_radio"))
        self.mapping_radio.setChecked(False)
        self.mapping_radio.toggled.connect(self.on_import_mode_changed)
        
        self.overwrite_radio = QtWidgets.QRadioButton(self.lm.get_string("EXPORT_DIALOG", "overwrite_radio"))
        self.overwrite_radio.setChecked(True)
        self.overwrite_radio.toggled.connect(self.on_import_mode_changed)
        
        mode_layout.addWidget(self.mapping_radio)
        mode_layout.addWidget(self.overwrite_radio)
        self.import_mode_group.setLayout(mode_layout)
        
        file_layout.addWidget(self.file_combo)
        file_layout.addWidget(self.new_file_name)
        file_layout.addWidget(self.import_mode_group)
        self.file_group.setLayout(file_layout)
        right_column.addWidget(self.file_group)

        # Слои и сопоставление полей
        self.mapping_group = QGroupBox(self.lm.get_string("EXPORT_DIALOG", "mapping_group"))
        self.mapping_group.setVisible(False)  # Изначально скрыт
        mapping_layout = QVBoxLayout()
        
        # Выбор слоя
        layer_label = QLabel(self.lm.get_string("EXPORT_DIALOG", "layer_select_label"))
        self.layer_combo = QComboBox()
        mapping_layout.addWidget(layer_label)
        mapping_layout.addWidget(self.layer_combo)
        
        # Вкладки сопоставления
        self.mapping_tabs = QTabWidget()
        self.mapping_tabs.setMinimumHeight(200)
        self.mapping_tabs.setVisible(False)  # Изначально скрыт
        
        # Вкладка геометрических объектов
        self.geom_tab = QtWidgets.QWidget()
        geom_layout = QVBoxLayout(self.geom_tab)
        self.geom_mapping_table = QTableWidget()
        self._setup_table(self.geom_mapping_table)
        geom_layout.addWidget(self.geom_mapping_table)
        self.mapping_tabs.addTab(self.geom_tab, self.lm.get_string("EXPORT_DIALOG", "geom_tab"))
        
        # Вкладка негеометрических объектов
        self.nongeom_tab = QtWidgets.QWidget()
        nongeom_layout = QVBoxLayout(self.nongeom_tab)
        self.nongeom_mapping_table = QTableWidget()
        self._setup_table(self.nongeom_mapping_table)
        nongeom_layout.addWidget(self.nongeom_mapping_table)
        self.mapping_tabs.addTab(self.nongeom_tab, self.lm.get_string("EXPORT_DIALOG", "nongeom_tab"))
        
        mapping_layout.addWidget(self.mapping_tabs)
        self.mapping_group.setLayout(mapping_layout)
        right_column.addWidget(self.mapping_group)

        # Кнопки внизу правой колонки
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.button(QDialogButtonBox.Ok).setText(self.lm.get_string("EXPORT_DIALOG", "ok_button"))
        self.buttonBox.button(QDialogButtonBox.Cancel).setText(self.lm.get_string("EXPORT_DIALOG", "cancel_button"))
        right_column.addWidget(self.buttonBox)
        
        # Добавляем разделитель, чтобы прижать все к верху
        right_column.addStretch()
        
        # Добавляем правый виджет в основной макет
        content_layout.addWidget(right_widget)

        # Добавляем основной макет в окно
        main_layout.addLayout(content_layout)

        # Начальная видимость
        self.mapping_group.hide()
        self.mapping_tabs.hide()

        # Подключение сигналов
        self._connect_signals()

    def _setup_table(self, table):
        """
        Вспомогательная функция для настройки таблицы сопоставлений.
        
        :param table: Таблица для настройки
        """
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels([
            self.lm.get_string("ATTRIBUTE_DIALOG", "dxf_attr_column"), 
            self.lm.get_string("ATTRIBUTE_DIALOG", "db_attr_column"),
            self.lm.get_string("EXPORT_DIALOG", "map_column")
        ])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setMinimumHeight(150)
        
        # Отключаем горизонтальную прокрутку
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Оптимизация для больших таблиц
        table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        
        # Оптимизация отрисовки
        table.setItemDelegate(OptimizedItemDelegate())

    def _connect_signals(self):
        """Подключение всех сигналов пользовательского интерфейса"""
        Logger.log_message("Подключение сигналов интерфейса")
        self.select_db_button.clicked.connect(self.on_select_db_button_clicked)
        self.info_button.clicked.connect(self.show_info_dialog)
        self.port_lineedit.textChanged.connect(self.on_port_changed)
        self.password_lineedit.textChanged.connect(self.on_password_changed)
        self.file_combo.currentIndexChanged.connect(self.on_file_selection_changed)
        self.new_file_name.textChanged.connect(self.on_new_file_name_changed)
        self.layer_combo.currentIndexChanged.connect(self.on_layer_changed)
        self.buttonBox.accepted.connect(self.on_ok_clicked)
        self.buttonBox.rejected.connect(self.on_cancel_clicked)

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
            self.load_available_tables()

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

    def refresh_data_dialog(self):
        """Обновление данных диалога на основе текущих настроек подключения"""
        Logger.log_message("Обновление данных диалога экспорта")
        self.address_label.setText(self.address)
        self.port_lineedit.setText(self.port)
        self.dbname_label.setText(self.dbname)
        self.schema_label.setText(self.schemaname)
        self.username_label.setText(self.username)
        self.password_lineedit.setText(self.password)
        self.show_window()
        self.populate_tree_widget()

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
                    self.load_available_tables()
                else:
                    Logger.log_error("Не удалось получить учетные данные для доступа к БД")
                    
                self.dlg = None
            else:
                Logger.log_message("Выбор базы данных отменен пользователем")

    def load_available_tables(self):
        """Загрузка доступных файлов из БД"""
        Logger.log_message("Загрузка доступных файлов из БД")
        try:
            self.file_combo.blockSignals(True)  # Блокируем сигналы, чтобы избежать нежелательных вызовов
            self.file_combo.clear()
            
            # Добавляем опцию "Новый файл" первой
            self.file_combo.addItem(self.lm.get_string("COMMON", "new_file"), None)
            
            # Получаем файлы только если имеется валидное подключение
            if self.dbname != 'none' and self.username != 'none':
                from ..db.database import get_all_files_from_db
                files = get_all_files_from_db(
                    self.username,
                    self.password,
                    self.address,
                    self.port,
                    self.dbname
                )
                
                if files:
                    Logger.log_message(f"Загружено {len(files)} файлов из БД")
                    for file_info in files:
                        try:
                            filename = file_info['filename']
                            upload_date = file_info['upload_date']
                            if upload_date:
                                display_text = f"{filename} ({upload_date.strftime('%Y-%m-%d')})"
                            else:
                                display_text = filename
                            self.file_combo.addItem(display_text, file_info['id'])
                        except Exception as e:
                            Logger.log_error(f"Ошибка добавления файла в выпадающий список: {str(e)}")
                            continue
                else:
                    Logger.log_message("В базе данных не найдено файлов")
            
            self.file_combo.blockSignals(False)  # Разблокируем сигналы
            self.file_combo.setCurrentIndex(0)
            
        except Exception as e:
            Logger.log_error(f"Ошибка загрузки файлов: {str(e)}")
            self.file_combo.clear()
            self.file_combo.addItem(self.lm.get_string("COMMON", "new_file"), None)

    def on_cancel_clicked(self):
        """Обработка нажатия кнопки Отмена"""
        Logger.log_message("Экспорт отменен пользователем")
        self.reject()

    def on_file_selection_changed(self, index):
        """
        Обработка изменения выбора файла.
        
        :param index: Индекс выбранного файла
        """
        try:
            self.selected_file_id = self.file_combo.currentData()
            self.is_new_file = self.selected_file_id is None
            
            Logger.log_message(f"Выбран {'новый' if self.is_new_file else 'существующий'} файл")
            
            # Включаем/отключаем ввод имени нового файла в зависимости от выбора
            self.new_file_name.setEnabled(self.is_new_file)
            if not self.is_new_file:
                self.new_file_name.clear()  # Очищаем текст если выбран существующий файл
            
            # Сбрасываем состояние UI
            self._reset_mapping_state()
            
            if not self.is_new_file:
                # Показываем режим импорта и управляем видимостью сопоставления
                self.import_mode_group.setVisible(True)
                item_text = self.file_combo.currentText()
                self.selected_file_name = item_text.split(' (')[0] if ' (' in item_text else item_text
                Logger.log_message(f"Выбран файл: {self.selected_file_name}")
                # Не показываем группу сопоставления по умолчанию, так как мы в режиме перезаписи
                self.mapping_group.setVisible(self.import_mode == 'mapping')
                if self.import_mode == 'mapping':
                    self.load_file_layers()
            else:
                # Скрываем оба режима импорта и сопоставления для новых файлов
                self.selected_file_name = None
                self.new_file_name.setEnabled(True)
                self.import_mode_group.setVisible(False)
                self.mapping_group.setVisible(False)
                self.mapping_tabs.setVisible(False)
                
        except Exception as e:
            Logger.log_error(f"Ошибка при выборе файла: {str(e)}")

    def _reset_mapping_state(self):
        """Сброс всех состояний, связанных с сопоставлением"""
        Logger.log_message("Сброс состояния сопоставления полей")
        self.mapping_tabs.hide()
        self.mapping_group.hide()
        self.import_mode_group.hide()  # Также скрываем режим импорта
        self.geom_mappings.clear()
        self.nongeom_mappings.clear()
        self.geom_mapping_table.clearContents()
        self.nongeom_mapping_table.clearContents()
        self.layer_combo.clear()

    def load_file_layers(self):
        """Загрузка слоев для выбранного файла"""
        try:
            Logger.log_message(f"Загрузка слоев для файла ID: {self.selected_file_id}")
            self.layer_combo.clear()
            
            if not self.selected_file_id:
                Logger.log_error("Файл не выбран")
                return
                
            # Получаем слои через новую функцию
            layers = get_layers_for_file(
                self.username,
                self.password,
                self.address,
                self.port,
                self.dbname,
                self.selected_file_id
            )

            if layers:
                self.layer_combo.blockSignals(True)
                
                # Если есть выбранные сущности, создаем множество их слоев
                selected_layers = set()
                if self.dxf_handler.selected_entities:
                    filename = self.dxf_tree_widget_handler.current_file_name
                    entities = self.dxf_handler.get_entities_for_export(filename)
                    selected_layers = {
                        entity.dxf.layer 
                        for entity in entities
                    }

                # Фильтруем и добавляем слои
                for layer in layers:
                    layer_id, name, color, description, metadata = layer
                    
                    # Пропускаем слои, которые не содержат выбранные объекты
                    if selected_layers and name not in selected_layers:
                        continue
                        
                    # Формируем текст для отображения
                    display_text = name if name else "Unnamed Layer"
                    
                    if color:
                        display_text += f" (color: {color})"
                    if description:
                        display_text += f" - {description}"
                        
                    # Добавляем элемент в комбобокс
                    self.layer_combo.addItem(display_text, layer_id)
                
                self.layer_combo.blockSignals(False)
                
                # Показываем группу маппинга если есть слои
                if self.layer_combo.count() > 0:
                    self.mapping_group.show()
                    self.layer_combo.setCurrentIndex(0)
                    
                    # Автоматически загружаем объекты для первого слоя
                    self.on_layer_changed(0)
                    
                    # Показываем вкладки маппинга только если в режиме маппинга
                    if self.import_mode == 'mapping':
                        self.mapping_tabs.show()
                else:
                    # Если нет доступных слоев для маппинга, показываем сообщение
                    if selected_layers:
                        QtWidgets.QMessageBox.information(
                            self,
                            self.lm.get_string("EXPORT_DIALOG", "info_title"),
                            self.lm.get_string("EXPORT_DIALOG", "no_layers_message")
                        )
                    Logger.log_error(f"No layers found for file {self.selected_file_id}")
                    self.mapping_group.hide()
                    self.mapping_tabs.hide()
                
        except Exception as e:
            Logger.log_error(f"Не удалось загрузить слои файла: {str(e)}")
            self.mapping_group.hide()
            self.mapping_tabs.hide()
            QtWidgets.QMessageBox.warning(
                self,
                self.lm.get_string("EXPORT_DIALOG", "error_title"),
                self.lm.get_string("EXPORT_DIALOG", "load_layers_error", str(e))
            )

    def on_layer_changed(self, index):
        """Обработка изменения выбора слоя"""
        try:
            self.selected_layer_id = self.layer_combo.currentData()
            if self.selected_layer_id:
                self.mapping_tabs.setVisible(True)
                self.geom_mapping_table.setVisible(True)
                self.nongeom_mapping_table.setVisible(True)
                self.load_field_mappings()
            else:
                self.mapping_tabs.setVisible(False)
        except Exception as e:
            Logger.log_error(f"Error in layer selection: {str(e)}")

    def load_field_mappings(self):
        """Загрузка сопоставлений для геометрических и негеометрических объектов"""
        if not self.selected_layer_id:
            return

        try:
            current_layer_text = self.layer_combo.currentText()
            layer_name = current_layer_text.split(" (")[0]
            
            # Обновляем заголовки вкладок
            self.mapping_tabs.setTabText(0, self.lm.get_string("EXPORT_DIALOG", "geom_tab_loading"))
            self.mapping_tabs.setTabText(1, self.lm.get_string("EXPORT_DIALOG", "nongeom_tab_loading"))
            QtWidgets.QApplication.processEvents()

            # Очищаем таблицы
            self.geom_mapping_table.clearContents()
            self.nongeom_mapping_table.clearContents()
            self.geom_mapping_table.setRowCount(0)
            self.nongeom_mapping_table.setRowCount(0)
            
            # Сбрасываем состояние пагинации при смене слоя
            if hasattr(self, 'pagination_widget_geom'):
                # Полностью скрываем элементы пагинации при смене слоя
                self.pagination_widget_geom.setVisible(False)
                self.pagination_widget_nongeom.setVisible(False)
                
                # Сбрасываем страницы
                self.current_page_geom = 1
                self.current_page_nongeom = 1
                
                # Очищаем сохраненные данные от предыдущего слоя
                self.all_geom_dxf = []
                self.all_nongeom_dxf = []
                self.all_geom_db_entities = []
                self.all_nongeom_db_entities = []
                
                # Обновляем текст лейблов пагинации
                self.page_label_geom.setText(self.lm.get_string("EXPORT_DIALOG", "page_label", 1, 1))
                self.page_label_nongeom.setText(self.lm.get_string("EXPORT_DIALOG", "page_label", 1, 1))
                
                # Отключаем кнопки пагинации
                self.prev_page_geom.setEnabled(False)
                self.next_page_geom.setEnabled(False)
                self.prev_page_nongeom.setEnabled(False)
                self.next_page_nongeom.setEnabled(False)
            
            # Пре-фильтрация сущностей DXF
            geom_dxf = []
            nongeom_dxf = []
            
            filename = self.dxf_tree_widget_handler.current_file_name
            
            # Прогресс диалог для загрузки сущностей
            progress = QProgressDialog(self.lm.get_string("EXPORT_DIALOG", "loading_layer_objects"), self.lm.get_string("COMMON", "cancel"), 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            QtWidgets.QApplication.processEvents()
            
            # Получаем сущности DXF для слоя
            if self.dxf_handler.selected_entities:
                entities_to_export = self.dxf_handler.get_entities_for_export(filename)
                
                progress.setLabelText(self.lm.get_string("EXPORT_DIALOG", "filtering_selected_entities"))
                progress.setValue(10)
                QtWidgets.QApplication.processEvents()
                
                # Фильтруем только выбранные сущности для текущего слоя
                selected_entities = [
                    entity for entity in entities_to_export
                    if entity.dxf.layer == layer_name
                ]
                
                total = len(selected_entities)
                for i, entity in enumerate(selected_entities):
                    if i % 50 == 0:
                        progress.setValue(10 + int(30 * i / total))
                        QtWidgets.QApplication.processEvents()
                        if progress.wasCanceled():
                            return
                            
                    entity_type = entity.dxftype()
                    entity_data = {
                        'handle': entity.dxf.handle,
                        'type': entity_type,
                        'entity': entity
                    }
                    if entity_type in ['TEXT', '3DSOLID']:
                        nongeom_dxf.append(entity_data)
                    else:
                        geom_dxf.append(entity_data)
            else:
                # Если нет выбранных сущностей, работаем со всем слоем
                progress.setLabelText(self.lm.get_string("EXPORT_DIALOG", "loading_all_layer_entities"))
                progress.setValue(20)
                QtWidgets.QApplication.processEvents()
                
                layer_entities = self.dxf_handler.get_layers(filename).get(layer_name, [])
                total = len(layer_entities)
                
                for i, entity in enumerate(layer_entities):
                    if i % 50 == 0:
                        progress.setValue(20 + int(20 * i / max(1, total)))
                        QtWidgets.QApplication.processEvents()
                        if progress.wasCanceled():
                            return
                            
                    entity_type = entity.dxftype()
                    entity_data = {
                        'handle': entity.dxf.handle,
                        'type': entity_type,
                        'entity': entity
                    }
                    if entity_type in ['TEXT', '3DSOLID']:
                        nongeom_dxf.append(entity_data)
                    else:
                        geom_dxf.append(entity_data)

            # Обновляем заголовки вкладок
            self.mapping_tabs.setTabText(0, self.lm.get_string("EXPORT_DIALOG", "geom_tab_count", len(geom_dxf)))
            self.mapping_tabs.setTabText(1, self.lm.get_string("EXPORT_DIALOG", "nongeom_tab_count", len(nongeom_dxf)))
            QtWidgets.QApplication.processEvents()

            if not geom_dxf and not nongeom_dxf:
                Logger.log_message(f"Сущности не найдены в слое {layer_name}")
                progress.close()
                return

            # Получаем сущности из базы данных
            progress.setLabelText(self.lm.get_string("EXPORT_DIALOG", "loading_db_objects"))
            progress.setValue(45)
            QtWidgets.QApplication.processEvents()
            
            db_entities = get_layer_objects(
                self.username,
                self.password,
                self.address,
                self.port,
                self.dbname,
                self.selected_layer_id
            )

            if not db_entities:
                progress.close()
                return

            # Разделяем геометрические и негеометрические сущности
            progress.setLabelText(self.lm.get_string("EXPORT_DIALOG", "processing_db_objects"))
            progress.setValue(60)
            QtWidgets.QApplication.processEvents()
            
            geom_db_entities = []
            nongeom_db_entities = []
            
            for i, entity in enumerate(db_entities):
                if i % 100 == 0:
                    progress.setValue(60 + int(20 * i / max(1, len(db_entities))))
                    QtWidgets.QApplication.processEvents()
                    if progress.wasCanceled():
                        return
                        
                try:
                    entity_id, geom_type, extra_data, obj_type = entity
                    if isinstance(extra_data, str):
                        import json
                        extra_data = json.loads(extra_data)
                    
                    handle = extra_data.get('attributes', {}).get('handle')
                    if handle:
                        entity_data = {
                            'id': entity_id,
                            'type': geom_type,
                            'handle': handle,
                            'extra_data': extra_data
                        }
                        if obj_type == 'geometric':
                            geom_db_entities.append(entity_data)
                        else:
                            nongeom_db_entities.append(entity_data)
                except Exception as e:
                    Logger.log_error(f"Error processing entity: {str(e)}")

            progress.setLabelText(self.lm.get_string("EXPORT_DIALOG", "setting_up_mapping_tables"))
            progress.setValue(85)
            QtWidgets.QApplication.processEvents()
            
            # Создаем отдельный оптимизатор таблиц
            table_optimizer = MappingTableOptimizer(self)

            # Определяем наличие крупного набора данных
            large_dataset = len(geom_dxf) > 200 or len(nongeom_dxf) > 200
            
            # Настраиваем и подключаем таблицы
            if large_dataset:
                # Для больших наборов данных используем пагинацию
                self._setup_pagination_controls()
                
                # Сохраняем данные для пагинации
                self.all_geom_dxf = geom_dxf
                self.all_nongeom_dxf = nongeom_dxf
                self.all_geom_db_entities = geom_db_entities
                self.all_nongeom_db_entities = nongeom_db_entities
                
                # Настраиваем только первую страницу
                self._load_current_page()
            else:
                # Для небольших наборов обычная настройка таблиц
                if geom_dxf:
                    table_optimizer.setup_mapping_table(
                        self.geom_mapping_table,
                        geom_dxf,
                        geom_db_entities,
                        self.geom_mappings
                    )

                if nongeom_dxf:
                    table_optimizer.setup_mapping_table(
                        self.nongeom_mapping_table,
                        nongeom_dxf,
                        nongeom_db_entities,
                        self.nongeom_mappings
                    )

            # Показываем таблицы
            self.geom_mapping_table.setVisible(True)
            self.nongeom_mapping_table.setVisible(True)
            
            progress.setValue(100)
            progress.close()
                
        except Exception as e:
            Logger.log_error(f"Failed to load field mappings: {str(e)}")
            import traceback
            Logger.log_error(traceback.format_exc())
            try:
                progress.close()
            except:
                pass

    def _setup_pagination_controls(self):
        """Настройка элементов управления пагинацией для больших таблиц"""
        # Создаем контейнеры для пагинации, если их еще нет
        if not hasattr(self, 'pagination_widget_geom'):
            # Геометрические объекты
            self.pagination_widget_geom = QtWidgets.QWidget()
            pagination_layout_geom = QtWidgets.QHBoxLayout(self.pagination_widget_geom)
            pagination_layout_geom.setContentsMargins(0, 0, 0, 0)
            
            self.prev_page_geom = QtWidgets.QPushButton("◄")
            self.prev_page_geom.setFixedWidth(40)
            self.page_label_geom = QtWidgets.QLabel(self.lm.get_string("EXPORT_DIALOG", "page_label", 1,1))
            self.next_page_geom = QtWidgets.QPushButton("►")
            self.next_page_geom.setFixedWidth(40)
            
            pagination_layout_geom.addWidget(self.prev_page_geom)
            pagination_layout_geom.addWidget(self.page_label_geom)
            pagination_layout_geom.addWidget(self.next_page_geom)
            
            # Встраиваем в вкладку
            geom_layout = self.geom_tab.layout()
            geom_layout.addWidget(self.pagination_widget_geom)

            # Негеометрические объекты
            self.pagination_widget_nongeom = QtWidgets.QWidget()
            pagination_layout_nongeom = QtWidgets.QHBoxLayout(self.pagination_widget_nongeom)
            pagination_layout_nongeom.setContentsMargins(0, 0, 0, 0)



            self.prev_page_nongeom = QtWidgets.QPushButton("◄")
            self.prev_page_nongeom.setFixedWidth(40)
            self.page_label_nongeom = QtWidgets.QLabel(self.lm.get_string("EXPORT_DIALOG", "page_label", 1,1))
            self.next_page_nongeom = QtWidgets.QPushButton("►")
            self.next_page_nongeom.setFixedWidth(40)
            
            pagination_layout_nongeom.addWidget(self.prev_page_nongeom)
            pagination_layout_nongeom.addWidget(self.page_label_nongeom)
            pagination_layout_nongeom.addWidget(self.next_page_nongeom)
            
            # Встраиваем в вкладку
            nongeom_layout = self.nongeom_tab.layout()
            nongeom_layout.addWidget(self.pagination_widget_nongeom)
            
            # Настройка параметров пагинации
            self.page_size = 100  # Элементов на страницу
            self.current_page_geom = 1
            self.current_page_nongeom = 1
            
            # Инициализируем пустые списки для данных
            self.all_geom_dxf = []
            self.all_nongeom_dxf = []
            self.all_geom_db_entities = []
            self.all_nongeom_db_entities = []
            
            # Подключаем обработчики
            self.prev_page_geom.clicked.connect(lambda: self._change_page('geom', -1))
            self.next_page_geom.clicked.connect(lambda: self._change_page('geom', 1))
            self.prev_page_nongeom.clicked.connect(lambda: self._change_page('nongeom', -1))
            self.next_page_nongeom.clicked.connect(lambda: self._change_page('nongeom', 1))
        
        # Обновляем видимость и состояние элементов пагинации
        self.pagination_widget_geom.setVisible(False)  # Изначально скрываем, покажем только если данных много
        self.pagination_widget_nongeom.setVisible(False)
        
        # Сбрасываем текущие страницы
        self.current_page_geom = 1
        self.current_page_nongeom = 1
        
        # Обновляем текст лейблов пагинации
        self.page_label_geom.setText(self.lm.get_string("EXPORT_DIALOG", "page_label", 1, 1))
        self.page_label_nongeom.setText(self.lm.get_string("EXPORT_DIALOG", "page_label", 1, 1))
        
        # Отключаем кнопки пагинации до загрузки данных
        self.prev_page_geom.setEnabled(False)
        self.next_page_geom.setEnabled(False)
        self.prev_page_nongeom.setEnabled(False)
        self.next_page_nongeom.setEnabled(False)

    def _change_page(self, table_type, direction):
        """
        Изменение текущей страницы данных для указанной таблицы
        
        :param table_type: Тип таблицы ('geom' или 'nongeom')
        :param direction: Направление изменения (1 - вперед, -1 - назад)
        """
        if table_type == 'geom':
            # Проверяем наличие данных
            if not self.all_geom_dxf:
                return
                
            new_page = self.current_page_geom + direction
            max_pages = max(1, (len(self.all_geom_dxf) + self.page_size - 1) // self.page_size)
            
            # Проверяем валидность новой страницы
            if 1 <= new_page <= max_pages:
                self.current_page_geom = new_page
                self._update_page_label('geom')
                self._load_page_data('geom')
                
        elif table_type == 'nongeom':
            # Проверяем наличие данных
            if not self.all_nongeom_dxf:
                return
                
            new_page = self.current_page_nongeom + direction
            max_pages = max(1, (len(self.all_nongeom_dxf) + self.page_size - 1) // self.page_size)
            
            # Проверяем валидность новой страницы
            if 1 <= new_page <= max_pages:
                self.current_page_nongeom = new_page
                self._update_page_label('nongeom')
                self._load_page_data('nongeom')

    def _update_page_label(self, table_type):
        """Обновление метки с номером текущей страницы"""
        if table_type == 'geom':
            # Если у нас нет данных, установим 0 страниц
            if not self.all_geom_dxf:
                total_pages = 1
                self.page_label_geom.setText(self.lm.get_string("EXPORT_DIALOG", "page_label", 1, 1))
                self.prev_page_geom.setEnabled(False)
                self.next_page_geom.setEnabled(False)
                self.pagination_widget_geom.setVisible(False)
                return
            
            total_pages = max(1, (len(self.all_geom_dxf) + self.page_size - 1) // self.page_size)
            self.page_label_geom.setText(self.lm.get_string("EXPORT_DIALOG", "page_label", 
                min(self.current_page_geom, total_pages), total_pages))
            
            # Обновляем состояние кнопок
            self.prev_page_geom.setEnabled(self.current_page_geom > 1)
            self.next_page_geom.setEnabled(self.current_page_geom < total_pages)
            
            # Обновляем видимость элементов пагинации
            self.pagination_widget_geom.setVisible(len(self.all_geom_dxf) > self.page_size)
            
        elif table_type == 'nongeom':
            # Если у нас нет данных, установим 0 страниц
            if not self.all_nongeom_dxf:
                total_pages = 1
                self.page_label_nongeom.setText(self.lm.get_string("EXPORT_DIALOG", "page_label", 1, 1))
                self.prev_page_nongeom.setEnabled(False)
                self.next_page_nongeom.setEnabled(False)
                self.pagination_widget_nongeom.setVisible(False)
                return
                
            total_pages = max(1, (len(self.all_nongeom_dxf) + self.page_size - 1) // self.page_size)
            self.page_label_nongeom.setText(self.lm.get_string("EXPORT_DIALOG", "page_label", 
                min(self.current_page_nongeom, total_pages), total_pages))
            
            # Обновляем состояние кнопок
            self.prev_page_nongeom.setEnabled(self.current_page_nongeom > 1)
            self.next_page_nongeom.setEnabled(self.current_page_nongeom < total_pages)
            
            # Обновляем видимость элементов пагинации
            self.pagination_widget_nongeom.setVisible(len(self.all_nongeom_dxf) > self.page_size)

    def _load_current_page(self):
        """Загружает текущую страницу для обеих таблиц"""
        self._update_page_label('geom')
        self._update_page_label('nongeom')
        self._load_page_data('geom')
        self._load_page_data('nongeom')

    def _load_page_data(self, table_type):
        """
        Загружает данные для указанной страницы в соответствующую таблицу
        
        :param table_type: Тип таблицы ('geom' или 'nongeom')
        """
        table_optimizer = MappingTableOptimizer(self)
        
        if table_type == 'geom':
            # Очищаем и настраиваем таблицу для текущей страницы
            self.geom_mapping_table.clearContents()
            self.geom_mapping_table.setRowCount(0)
            
            # Проверяем существование данных
            if not self.all_geom_dxf:
                return
                
            start_idx = (self.current_page_geom - 1) * self.page_size
            # Проверяем валидность индекса
            if start_idx >= len(self.all_geom_dxf):
                # Если текущий индекс за пределами массива, сбрасываем на первую страницу
                self.current_page_geom = 1
                start_idx = 0
                self._update_page_label('geom')
                
            end_idx = min(start_idx + self.page_size, len(self.all_geom_dxf))
            page_items = self.all_geom_dxf[start_idx:end_idx]
            
            if page_items:
                table_optimizer.setup_mapping_table(
                    self.geom_mapping_table,
                    page_items,
                    self.all_geom_db_entities,
                    self.geom_mappings
                )
        
        elif table_type == 'nongeom':
            # Очищаем и настраиваем таблицу для текущей страницы
            self.nongeom_mapping_table.clearContents()
            self.nongeom_mapping_table.setRowCount(0)
            
            # Проверяем существование данных
            if not self.all_nongeom_dxf:
                return
                
            start_idx = (self.current_page_nongeom - 1) * self.page_size
            # Проверяем валидность индекса
            if start_idx >= len(self.all_nongeom_dxf):
                # Если текущий индекс за пределами массива, сбрасываем на первую страницу
                self.current_page_nongeom = 1
                start_idx = 0
                self._update_page_label('nongeom')
                
            end_idx = min(start_idx + self.page_size, len(self.all_nongeom_dxf))
            page_items = self.all_nongeom_dxf[start_idx:end_idx]
            
            if page_items:
                table_optimizer.setup_mapping_table(
                    self.nongeom_mapping_table,
                    page_items,
                    self.all_nongeom_db_entities,
                    self.nongeom_mappings
                )

    def on_ok_clicked(self):
        """Обработка нажатия кнопки OK"""

        file_name = self.new_file_name.text().strip() if self.is_new_file else None
        if self.is_new_file:
            if not file_name:
                QtWidgets.QMessageBox.warning(self, self.lm.get_string("EXPORT_DIALOG", "warning_title"), self.lm.get_string("EXPORT_DIALOG", "enter_file_name_warning"))
                return
                
            # Повторная проверка существования файла перед сохранением
            try:
                from ..db.database import check_file_exists
                file_exists = check_file_exists(file_name)
                
                if file_exists:
                    QtWidgets.QMessageBox.warning(
                        self,
                        self.lm.get_string("EXPORT_DIALOG", "warning_title"),
                        self.lm.get_string("EXPORT_DIALOG", "file_exists_warning")
                    )
                    return
            except Exception as e:
                Logger.log_error(f"Ошибка проверки файла: {str(e)}")
                QtWidgets.QMessageBox.critical(
                    self,
                    self.lm.get_string("EXPORT_DIALOG", "error_title"),
                    self.lm.get_string("EXPORT_DIALOG", "check_file_error", str(e))
                )
                return

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
        
        # Подготавливаем информацию для экспорта
        table_info = {
            'is_new_file': self.is_new_file,
            'file_id': self.selected_file_id,
            'layer_id': self.selected_layer_id,
            'new_file_name': file_name,
            'import_mode': self.import_mode,
            'geom_mappings': self.geom_mappings if not self.is_new_file and self.import_mode == 'mapping' else None,
            'nongeom_mappings': self.nongeom_mappings if not self.is_new_file and self.import_mode == 'mapping' else None
        }
        
        # Создаем и запускаем поток экспорта
        self.export_thread = ExportThread(
            self.username,
            self.password,
            self.address,
            self.port,
            self.dbname,
            self.dxf_handler,
            table_info
        )
        self.export_thread.finished.connect(self.on_export_finished)
        self.export_thread.start()
        
        # Показываем прогресс
        self.progress.show()

    def update_progress_text(self):
        """Обновление текста в окне прогресса"""
        self.dots = (self.dots + 1) % 4
        self.progress.setLabelText(self.lm.get_string("EXPORT_DIALOG", "export_progress") + '.' * self.dots)

    def on_export_finished(self, success, message):
        """Обработка завершения экспорта"""
        self.timer.stop()
        self.progress.close()
        
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

    def on_cancel_clicked(self):
        """Обработка нажатия кнопки Отмена"""
        self.reject()

    def on_new_file_name_changed(self, text):
        """Обработка изменения имени нового файла"""
        if self.is_new_file:
            self.mapping_group.setVisible(False)
            self.geom_mappings = {}
            self.nongeom_mappings = {}
            self.geom_mapping_table.clearContents()
            self.nongeom_mapping_table.clearContents()
            
            # Проверяем существование файла с таким именем
            if text.strip():
                try:
                    from ..db.database import check_file_exists
                    file_exists = check_file_exists(text.strip())
                    
                    if file_exists:
                        # Красный фон и подсказка при существующем файле
                        self.new_file_name.setStyleSheet("background-color: #ffcccc;")
                        self.new_file_name.setToolTip(self.lm.get_string("EXPORT_DIALOG", "file_exists_tooltip"))
                        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
                    else:
                        # Нормальный фон и очистка подсказки при уникальном имени
                        self.new_file_name.setStyleSheet("background-color: #ffffff;")
                        self.new_file_name.setToolTip(self.lm.get_string("EXPORT_DIALOG", "file_name_available_tooltip"))
                        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)
                except Exception as e:
                    # Желтый фон и подсказка при ошибке проверки
                    self.new_file_name.setStyleSheet("background-color: #fff3cd;")
                    self.new_file_name.setToolTip(self.lm.get_string("EXPORT_DIALOG", "check_file_error_tooltip", str(e)))
                    Logger.log_error(f"Ошибка проверки файла: {str(e)}")
            else:
                # Сброс стиля и подсказки при пустом имени
                self.new_file_name.setStyleSheet("")
                self.new_file_name.setToolTip(self.lm.get_string("EXPORT_DIALOG", "enter_file_name_tooltip"))
                self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)

    def on_import_mode_changed(self, checked):
        """Обработка изменения режима импорта"""
        if checked:
            if self.mapping_radio.isChecked():
                self.import_mode = 'mapping'
                if not self.is_new_file:
                    self.mapping_group.setVisible(True)
                    self.load_file_layers()
            else:
                self.import_mode = 'overwrite'
                self.mapping_group.setVisible(False)
                self.mapping_tabs.setVisible(False)

class OptimizedItemDelegate(QtWidgets.QStyledItemDelegate):
    """Оптимизированный делегат для элементов таблицы с редкой отрисовкой"""
    def paint(self, painter, option, index):
        # Оптимизированная отрисовка только видимых ячеек
        if option.rect.intersects(painter.viewport()):
            super().paint(painter, option, index)


class MappingTableOptimizer:
    """
    Класс для оптимизированной настройки таблиц сопоставления.
    Отделяет логику создания таблицы от основного класса.
    """
    def __init__(self, parent):
        """
        Инициализация оптимизатора
        
        :param parent: Родительский виджет
        """
        self.parent = parent

    def setup_mapping_table(self, table, dxf_entities, db_entities, mappings):
        """Настройка таблицы сопоставлений с оптимизацией производительности"""
        try:
            table.blockSignals(True)
            table.setRowCount(0)  # Сбрасываем количество строк
            
            # Подготовка базы данных сущностей для быстрого поиска
            db_handle_map = {entity['handle']: entity for entity in db_entities}
            
            # Заранее создаем все строки таблицы
            table.setRowCount(len(dxf_entities))
            
            # Для оптимизации будем обновлять только по 20 строк за раз
            batch_size = 20
            total_batches = (len(dxf_entities) + batch_size - 1) // batch_size
            
            for batch_idx in range(total_batches):
                start = batch_idx * batch_size
                end = min(start + batch_size, len(dxf_entities))
                
                # Создаем строки для текущего пакета
                for i in range(start, end):
                    dxf_entity = dxf_entities[i]
                    self._create_table_row_optimized(table, i, dxf_entity, db_handle_map, db_entities, mappings)
                
                # Обновляем интерфейс после каждого пакета строк
                if (batch_idx + 1) % 2 == 0 or batch_idx == total_batches - 1:
                    QtWidgets.QApplication.processEvents()
            
            table.blockSignals(False)
                
        except Exception as e:
            Logger.log_error(f"Ошибка при настройке таблицы сопоставлений: {str(e)}")
            import traceback
            Logger.log_error(traceback.format_exc())

    def _create_table_row_optimized(self, table, row_idx, dxf_entity, db_handle_map, db_entities, mappings):
        """Оптимизированное создание одной строки в таблице сопоставлений"""
        # Текст сущности
        dxf_text = f"{dxf_entity['type']}(#{dxf_entity['handle']})"
        dxf_item = QtWidgets.QTableWidgetItem(dxf_text)
        dxf_item.setFlags(dxf_item.flags() & ~Qt.ItemIsEditable)
        
        handle = dxf_entity['handle']
        is_new = handle not in db_handle_map
        
        if is_new:
            dxf_item.setBackground(Qt.yellow)
            dxf_item.setToolTip(self.parent.lm.get_string("EXPORT_DIALOG", "new_entity_tooltip"))
        
        table.setItem(row_idx, 0, dxf_item)
        
        # Создаем и настраиваем контейнер для комбобокса
        combo_container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(combo_container)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # Используем кэширование для оптимизации
        handle_cache = getattr(self, '_handle_cache', {})
        if handle in handle_cache:
            combo = handle_cache[handle]
        else:
            combo = self._create_combo_for_entity(handle, dxf_entity, db_handle_map, db_entities, mappings)
            handle_cache[handle] = combo
        
        setattr(self, '_handle_cache', handle_cache)
        
        layout.addWidget(combo)
        table.setCellWidget(row_idx, 1, combo_container)
        
        # Кнопка атрибутов - создаем, только если нажата
        attr_button = QtWidgets.QPushButton(self.parent.lm.get_string("EXPORT_DIALOG", "attributes_button"))
        attr_button.clicked.connect(
            lambda checked, h=handle, e=dxf_entity, d=db_handle_map.get(handle):
                self._show_attributes_dialog(h, e, d, mappings)
        )
        table.setCellWidget(row_idx, 2, attr_button)

    def _create_combo_for_entity(self, handle, dxf_entity, db_handle_map, db_entities, mappings):
        """Создание оптимизированного комбобокса для сущности"""
        combo = QtWidgets.QComboBox()
        combo.setMaxVisibleItems(15)  # Оптимизация отображения выпадающего списка
        
        # Добавляем пустой вариант
        combo.addItem('', None)
        
        # Добавляем соответствующую сущность из БД, если она существует
        found_match = False
        if handle in db_handle_map:
            db_entity = db_handle_map[handle]
            display_text = f"{db_entity['type']}(#{db_entity['handle']})"
            combo.addItem(display_text, db_entity['id'])
            combo.setCurrentIndex(1)  # Выбираем соответствующее значение
            
            # Сохраняем сопоставление
            mappings[handle] = {
                'entity_id': db_entity['id'],
                'attributes': {}
            }
            
            found_match = True
        
        # Если не нашли соответствие, добавим 5 первых вариантов + многоточие
        if not found_match and len(db_entities) > 0:
            # Добавляем только несколько элементов для производительности
            for i, entity in enumerate(db_entities[:5]):
                display_text = f"{entity['type']}(#{entity['handle']})"
                combo.addItem(display_text, entity['id'])
                
            # Если элементов больше, добавим специальный пункт "Больше..."
            if len(db_entities) > 5:
                combo.addItem(self.parent.lm.get_string("EXPORT_DIALOG", "more_items"), "more_items")
                # Подключаем обработчик для динамической загрузки
                combo.activated.connect(
                    lambda idx, c=combo, db=db_entities:
                        self._handle_combo_more_selection(idx, c, db, mappings, handle)
                )
        
        # Подключаем обработчик изменения
        combo.currentIndexChanged.connect(
            lambda idx, h=handle, c=combo:
                self._on_entity_mapping_changed(h, c.currentData(), mappings)
        )
        
        return combo

    def _handle_combo_more_selection(self, idx, combo, db_entities, mappings, handle):
        """Обработчик выбора пункта 'Больше...' в выпадающем списке"""
        if combo.currentData() == "more_items":
            # Блокируем сигналы комбобокса
            combo.blockSignals(True)
            
            # Запоминаем текущий текст
            current_text = combo.currentText()
            
            # Очищаем комбобокс
            combo.clear()
            
            # Добавляем пустой элемент
            combo.addItem('', None)
            
            # Добавляем пункт "Вернуться к сокращенному списку"
            combo.addItem(self.parent.lm.get_string("EXPORT_DIALOG", "back"), "back")
            
            # Добавляем все элементы
            for entity in db_entities:
                display_text = f"{entity['type']}(#{entity['handle']})"
                combo.addItem(display_text, entity['id'])
            
            # Разблокируем сигналы и выбираем первый элемент
            combo.blockSignals(False)
            combo.setCurrentIndex(0)
            
            # Показываем выпадающий список
            combo.showPopup()
        elif combo.currentData() == "back":
            # Возвращаемся к сокращенному списку
            combo.blockSignals(True)
            combo.clear()
            combo.addItem('', None)
            
            # Добавляем первые 5 элементов
            for i, entity in enumerate(db_entities[:5]):
                display_text = f"{entity['type']}(#{entity['handle']})"
                combo.addItem(display_text, entity['id'])
                
            combo.addItem(self.parent.lm.get_string("EXPORT_DIALOG", "more_items"), "more_items")
            combo.blockSignals(False)
            combo.setCurrentIndex(0)
            
            # Сбрасываем маппинг
            if handle in mappings:
                del mappings[handle]

    def _on_entity_mapping_changed(self, dxf_handle, db_id, mappings):
        """Обновление сопоставления при изменении выбора объекта"""
        if db_id and db_id not in ["more_items", "back"]:
            mappings[dxf_handle] = {
                'entity_id': db_id,
                'attributes': {}
            }
        elif db_id is None:
            mappings.pop(dxf_handle, None)

    def _show_attributes_dialog(self, handle, dxf_entity, db_entity, mappings):
        """Показать атрибуты в отдельном диалоговом окне"""
        from .attribute_dialog import AttributeDialog
        dialog = AttributeDialog(dxf_entity, db_entity, self.parent)
        if dialog.exec_() == QDialog.Accepted:
            if handle in mappings:
                mappings[handle]['attributes'] = dialog.get_mapped_attributes()
