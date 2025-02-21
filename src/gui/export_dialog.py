from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                           QTreeWidget, QLabel, QPushButton, QLineEdit, QWidget, 
                           QComboBox, QTabWidget, QTableWidget, QDialogButtonBox,
                           QHeaderView, QTreeWidgetItem)
from qgis.core import QgsSettings

from ..db.saved_connections_manager import *
from ..tree_widget_handler import TreeWidgetHandler
from ..logger.logger import Logger
from ..dxf.dxf_handler import DXFHandler
from ..db.database import export_dxf
from ..db.database import (get_layer_objects, get_layers_for_file, get_table_fields)
from .info_dialog import InfoDialog
from ..config.help_content import EXPORT_DIALOG_HELP


class ExportDialog(QDialog):
    def __init__(self, dxf_tree_widget_handler: TreeWidgetHandler, dxf_handler: DXFHandler, parent=None):
        super().__init__(parent)
        self.dxf_tree_widget_handler = dxf_tree_widget_handler
        self.dxf_handler = dxf_handler
        
        # Инициализируем переменные
        self.selected_file_id = None
        self.is_new_file = True
        self.selected_file_name = None
        self.selected_layer_id = None
        self.geom_mappings = {}
        self.nongeom_mappings = {}
        self.import_mode = 'overwrite'  # Меняем режим по умолчанию на "Overwrite"
        self.dlg = None 

        # Параметры БД
        self.address = 'none'
        self.port = '5432'
        self.dbname = 'none'
        self.username = 'none'
        self.password = 'none'
        self.schemaname = 'none'

        self.setup_ui()
        
        self.load_last_connection()

    def setup_ui(self):
        """Создание и настройка элементов пользовательского интерфейса"""
        self.setWindowTitle("Export to Database")
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
        
        # Группа DXF объектов
        self.dxf_group = QGroupBox("DXF Objects")
        dxf_layout = QVBoxLayout()
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setColumnCount(1)  # Изменено на 1 колонку
        self.tree_widget.setMinimumHeight(300)
        self.tree_widget.setMinimumWidth(400)  # Установим минимальную ширину
        dxf_layout.addWidget(self.tree_widget)
        self.dxf_group.setLayout(dxf_layout)
        left_column.addWidget(self.dxf_group)

        # Группа подключения к базе данных
        self.connection_group = QGroupBox("Database Connection")
        conn_layout = QVBoxLayout()
        
        # Строка адреса
        addr_layout = QHBoxLayout()
        self.address_label = QLabel()
        self.select_db_button = QPushButton("Select DB")
        addr_layout.addWidget(QLabel("Address:"))
        addr_layout.addWidget(self.address_label)
        addr_layout.addWidget(self.select_db_button)
        conn_layout.addLayout(addr_layout)
        
        # Строка порта
        port_layout = QHBoxLayout()
        self.port_lineedit = QLineEdit()
        port_layout.addWidget(QLabel("Port:"))
        port_layout.addWidget(self.port_lineedit)
        conn_layout.addLayout(port_layout)
        
        # Строка имени БД
        db_layout = QHBoxLayout()
        self.dbname_label = QLabel()
        db_layout.addWidget(QLabel("DB Name:"))
        db_layout.addWidget(self.dbname_label)
        conn_layout.addLayout(db_layout)
        
        # Строка схемы
        schema_layout = QHBoxLayout()
        self.schema_label = QLabel()
        schema_layout.addWidget(QLabel("Schema:"))
        schema_layout.addWidget(self.schema_label)
        conn_layout.addLayout(schema_layout)
        
        # Строка имени пользователя
        user_layout = QHBoxLayout()
        self.username_label = QLabel()
        user_layout.addWidget(QLabel("Username:"))
        user_layout.addWidget(self.username_label)
        conn_layout.addLayout(user_layout)
        
        # Строка пароля
        pass_layout = QHBoxLayout()
        self.password_lineedit = QLineEdit()
        self.password_lineedit.setEchoMode(QLineEdit.Password)
        pass_layout.addWidget(QLabel("Password:"))
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
        self.file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout()
        
        # Выбор существующего файла и ввод имени
        self.file_combo = QComboBox()
        self.new_file_name = QLineEdit()
        self.new_file_name.setPlaceholderText("Enter new file name")
        
        # Выбор режима импорта
        self.import_mode_group = QGroupBox("Import Mode")
        self.import_mode_group.setVisible(False)  # Изначально скрыт
        mode_layout = QVBoxLayout()
        
        self.mapping_radio = QtWidgets.QRadioButton("Field Mapping")
        self.mapping_radio.setChecked(False)  # Изменено состояние по умолчанию
        self.mapping_radio.toggled.connect(self.on_import_mode_changed)
        
        self.overwrite_radio = QtWidgets.QRadioButton("Overwrite File")
        self.overwrite_radio.setChecked(True)  # Изменено состояние по умолчанию
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
        self.mapping_group = QGroupBox("Layer and Field Mapping")
        self.mapping_group.setVisible(False)  # Изначально скрыт
        mapping_layout = QVBoxLayout()
        
        # Выбор слоя
        layer_label = QLabel("Select Layer:")
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
        self.mapping_tabs.addTab(self.geom_tab, "Geometric Objects")
        
        # Вкладка негеометрических объектов
        self.nongeom_tab = QtWidgets.QWidget()
        nongeom_layout = QVBoxLayout(self.nongeom_tab)
        self.nongeom_mapping_table = QTableWidget()
        self._setup_table(self.nongeom_mapping_table)
        nongeom_layout.addWidget(self.nongeom_mapping_table)
        self.mapping_tabs.addTab(self.nongeom_tab, "Non-Geometric Objects")
        
        mapping_layout.addWidget(self.mapping_tabs)
        self.mapping_group.setLayout(mapping_layout)
        right_column.addWidget(self.mapping_group)

        # Кнопки внизу правой колонки
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
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
        """Вспомогательная функция для настройки таблицы сопоставлений"""
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["DXF Field", "DB Field"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setMinimumHeight(150)

    def _connect_signals(self):
        """Подключение всех сигналов пользовательского интерфейса"""
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
        dialog = InfoDialog("Export Dialog Help", EXPORT_DIALOG_HELP, self)
        dialog.exec_()

    def load_last_connection(self):
        """Загрузка последнего использованного подключения к базе данных из настроек QGIS"""
        settings = QgsSettings()
        self.address = settings.value("DXFPostGIS/lastConnection/host", 'none')
        self.port = settings.value("DXFPostGIS/lastConnection/port", '5432')
        self.dbname = settings.value("DXFPostGIS/lastConnection/database", 'none')
        self.username = settings.value("DXFPostGIS/lastConnection/username", 'none')
        self.password = settings.value("DXFPostGIS/lastConnection/password", 'none')
        self.schemaname = settings.value("DXFPostGIS/lastConnection/schema", 'none')

        if self.dbname != 'none':
            self.refresh_data_dialog()
            self.load_available_tables()

    def save_current_connection(self):
        """Сохранение текущего подключения к базе данных в настройках QGIS"""
        settings = QgsSettings()
        settings.setValue("DXFPostGIS/lastConnection/host", self.address)
        settings.setValue("DXFPostGIS/lastConnection/port", self.port)
        settings.setValue("DXFPostGIS/lastConnection/database", self.dbname)
        settings.setValue("DXFPostGIS/lastConnection/username", self.username)
        settings.setValue("DXFPostGIS/lastConnection/password", self.password)
        settings.setValue("DXFPostGIS/lastConnection/schema", self.schemaname)

    def on_port_changed(self, text):
        self.port = text


    def on_password_changed(self, text):
        self.password = text


    def copy_checked_items(self, parent_item, new_parent_item):
        """Рекурсивная функция для копирования всех отмеченных (Checked) дочерних элементов из дерева"""
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
        """Заполнение древовидного виджета"""
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
        self.address_label.setText(self.address)
        self.port_lineedit.setText(self.port)
        self.dbname_label.setText(self.dbname)
        self.schema_label.setText(self.schemaname)
        self.username_label.setText(self.username)
        self.password_lineedit.setText(self.password)
        self.show_window()
        self.populate_tree_widget()



    def show_window(self):
        # Показать окно и сделать его активным
        self.raise_()
        self.activateWindow()
        self.show()


    def on_select_db_button_clicked(self):
        from .providers_dialog import ProvidersDialog

        if self.dlg is None:
            self.dlg = ProvidersDialog()
            self.dlg.show()
            result = self.dlg.exec_()

            if result and self.dlg.db_tree.currentSchema() is not None:
                self.address = self.dlg.db_tree.currentDatabase().connection().db.connector.host
                self.dbname = self.dlg.db_tree.currentDatabase().connection().db.connector.dbname
                self.username = self.dlg.db_tree.currentDatabase().connection().db.connector.user
                self.schemaname = self.dlg.db_tree.currentSchema().name
                conn = get_connection(self.dbname)
                self.password = conn['password'] if conn is not None else self.password
                self.save_current_connection()

            self.refresh_data_dialog()
            self.load_available_tables()

    def load_available_tables(self):
        """Загрузка доступных файлов из БД"""
        try:
            self.file_combo.blockSignals(True)  # Блокируем сигналы, чтобы избежать нежелательных вызовов
            self.file_combo.clear()
            
            # Добавляем опцию "Новый файл" первой
            self.file_combo.addItem("New File", None)
            
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
                            Logger.log_error(f"Failed to add file to combo box: {str(e)}")
                            continue
            
            self.file_combo.blockSignals(False)  # Разблокируем сигналы
            self.file_combo.setCurrentIndex(0)
            
        except Exception as e:
            Logger.log_error(f"Failed to load files: {str(e)}")
            self.file_combo.clear()
            self.file_combo.addItem("New File", None)

    def on_file_changed(self, index):
        """Обработка изменения выбора файла"""
        try:
            self.selected_file_id = self.file_combo.currentData()
            use_existing = self.selected_file_id is not None
            
            # Очистить предыдущее состояние
            self.table_combo.clear()
            self.field_mappings = {}
            
            # Включить/отключить элементы управления
            self.new_table_radio.setEnabled(not use_existing)
            self.existing_table_radio.setEnabled(use_existing)
            self.new_table_name.setEnabled(not use_existing)
            
            if use_existing:
                self.existing_table_radio.setChecked(True)
                self.load_file_tables()
            else:
                self.new_table_radio.setChecked(True)
        except Exception as e:
            Logger.log_error(f"Ошибка при выборе файла: {str(e)}")

    def load_file_tables(self):
        """Загрузка таблиц, связанных с выбранным файлом"""
        if not self.selected_file_id:
            return
            
        try:
            self.table_combo.clear()
            from ..db.database import get_all_file_layers_from_db
            
            layers = get_all_file_layers_from_db(
                self.username,
                self.password,
                self.address,
                self.port,
                self.dbname,
                self.selected_file_id
            )
            
            if layers:
                for layer in layers:
                    try:
                        name = layer.get('name', '')
                        if name:
                            self.table_combo.addItem(name)
                    except Exception as e:
                        Logger.log_error(f"Failed to add layer to combo box: {str(e)}")
                        continue
            
        except Exception as e:
            Logger.log_error(f"Failed to load file tables: {str(e)}")

    def on_table_changed(self, table_name):
        """Обработка изменения выбора таблицы"""
        if not table_name:
            return
            
        self.selected_table = table_name
        self.load_field_mapping()

    def load_field_mapping(self):
        """Загрузка доступных полей для сопоставления между DXF и выбранной таблицей"""
        if not self.selected_file_name:
            return
            
        try:
            # Получаем основные поля DXF (на основе наших моделей базы данных)
            dxf_fields = [
                'file_id',
                'layer_id', 
                'geom_type',
                'geometry',
                'extra_data'
            ]
            
            # Добавляем дополнительные поля из DXF
            if hasattr(self.dxf_handler, 'get_additional_fields'):
                dxf_fields.extend(self.dxf_handler.get_additional_fields())
            
            # Получаем поля таблицы с использованием новой функции базы данных
            table_fields = get_table_fields(
                self.username,
                self.password,
                self.address,
                self.port,
                self.dbname,
                self.schemaname,
                self.selected_file_name
            )

            if table_fields is None:
                return

            for i, dxf_field in enumerate(dxf_fields):
                # Создаем элемент для поля DXF
                dxf_item = QtWidgets.QTableWidgetItem(dxf_field)
                # Делаем только для чтения
                dxf_item.setFlags(dxf_item.flags() & ~Qt.ItemIsEditable)
                
                # Создаем комбобокс для поля таблицы
                combo = QtWidgets.QComboBox()
                combo.addItems([''] + table_fields)
                
                # Автоматически выбираем совпадающие имена полей
                if dxf_field in table_fields:
                    combo.setCurrentText(dxf_field)
                    self.field_mappings[dxf_field] = dxf_field
                
                combo.currentTextChanged.connect(
                    lambda text, field=dxf_field: self.on_mapping_changed(field, text)
                )

        except Exception as e:
            Logger.log_error(f"Не удалось загрузить сопоставление полей: {str(e)}")

    def on_mapping_changed(self, dxf_field, table_field):
        """Обновление сопоставления полей при изменении выбора"""
        if table_field:
            self.field_mappings[dxf_field] = table_field
        else:
            self.field_mappings.pop(dxf_field, None)

    def on_ok_clicked(self):
        """Обработка нажатия кнопки OK"""
        add_connection(self.dbname, self.username, self.password)
        
        file_name = self.new_file_name.text().strip() if self.is_new_file else None
        if self.is_new_file and not file_name:
            QtWidgets.QMessageBox.warning(
                self, 
                "Warning", 
                "Please enter a file name"
            )
            return
                
        table_info = {
            'is_new_file': self.is_new_file,
            'file_id': self.selected_file_id,
            'new_file_name': file_name,
            'field_mappings': self.field_mappings if not self.is_new_file else None
        }
        
        export_dxf(
            self.username,
            self.password,                
            self.address,                   
            self.port,                  
            self.dbname,
            self.dxf_handler,
            table_info
        )
        self.accept()

    def on_cancel_clicked(self):
        """Обработка нажатия кнопки Отмена"""
        self.reject()

    def on_file_selection_changed(self, index):
        """Обработка изменения выбора файла"""
        try:
            self.selected_file_id = self.file_combo.currentData()
            self.is_new_file = self.selected_file_id is None
            
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
            Logger.log_error(f"Error in file selection: {str(e)}")

    def _reset_mapping_state(self):
        """Сброс всех состояний, связанных с сопоставлением"""
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
                for layer in layers:
                    layer_id, name, color, description, metadata = layer
                    
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
                Logger.log_error(f"No layers found for file {self.selected_file_id}")
                self.mapping_group.hide()
                self.mapping_tabs.hide()
                
        except Exception as e:
            Logger.log_error(f"Не удалось загрузить слои файла: {str(e)}")
            self.mapping_group.hide()
            self.mapping_tabs.hide()
            QtWidgets.QMessageBox.warning(
                self,
                "Ошибка",
                f"Не удалось загрузить слои: {str(e)}"
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
            self.mapping_tabs.setTabText(0, "Geometric Objects (Loading...)")
            self.mapping_tabs.setTabText(1, "Non-Geometric Objects (Loading...)")
            QtWidgets.QApplication.processEvents()

            # Очищаем таблицы
            self.geom_mapping_table.clearContents()
            self.nongeom_mapping_table.clearContents()
            self.geom_mapping_table.setRowCount(0)
            self.nongeom_mapping_table.setRowCount(0)
            
            # Пре-фильтрация сущностей DXF
            geom_dxf = []
            nongeom_dxf = []
            
            # Получаем сущности DXF для слоя со считыванием всех файлов
            for filename in self.dxf_handler.dxf:
                layer_entities = self.dxf_handler.get_layers(filename).get(layer_name, [])
                for entity in layer_entities:
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
            self.mapping_tabs.setTabText(0, f"Geometric Objects ({len(geom_dxf)})")
            self.mapping_tabs.setTabText(1, f"Non-Geometric Objects ({len(nongeom_dxf)})")
            QtWidgets.QApplication.processEvents()

            if not geom_dxf and not nongeom_dxf:
                Logger.log_message(f"No entities found in layer {layer_name}")
                return

            # Получаем сущности из базы данных
            db_entities = get_layer_objects(
                self.username,
                self.password,
                self.address,
                self.port,
                self.dbname,
                self.selected_layer_id
            )

            if not db_entities:
                return

            # Разделяем геометрические и негеометрические сущности
            geom_db_entities = []
            nongeom_db_entities = []
            
            for entity in db_entities:
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

            # Устанавливаем пакетную обработку для таблиц
            BATCH_SIZE = 50
            
            if geom_dxf:
                self._setup_mapping_table_batch(
                    self.geom_mapping_table,
                    geom_dxf,
                    geom_db_entities,
                    self.geom_mappings,
                    BATCH_SIZE
                )

            if nongeom_dxf:
                self._setup_mapping_table_batch(
                    self.nongeom_mapping_table,
                    nongeom_dxf,
                    nongeom_db_entities,
                    self.nongeom_mappings,
                    BATCH_SIZE
                )

            # Показываем таблицы
            self.geom_mapping_table.setVisible(True)
            self.nongeom_mapping_table.setVisible(True)
                
        except Exception as e:
            Logger.log_error(f"Failed to load field mappings: {str(e)}")

    def _setup_mapping_table_batch(self, table, dxf_entities, db_entities, mappings, batch_size):
        """Настройка таблицы сопоставлений с пакетной обработкой"""
        try:
            table.blockSignals(True)
            table.setColumnCount(3)
            table.setHorizontalHeaderLabels(['DXF Entity', 'DB Entity', 'Actions'])
            table.setRowCount(len(dxf_entities))
            
            # Устанавливаем равномерное распределение столбцов
            header = table.horizontalHeader()
            for i in range(3):
                header.setSectionResizeMode(i, QHeaderView.Stretch)
            
            # Создаем поиск для объектов БД
            db_handle_map = {entity['handle']: entity for entity in db_entities}
            
            # Обрабатываем сущности пакетами
            for i in range(0, len(dxf_entities), batch_size):
                batch = dxf_entities[i:i + batch_size]
                
                for j, dxf_entity in enumerate(batch, i):
                    self._create_table_row(table, j, dxf_entity, db_handle_map, db_entities, mappings)
                    
                    # Обновляем UI каждые 10 строк
                    if (j + 1) % 10 == 0:  
                        QtWidgets.QApplication.processEvents()
            
            table.blockSignals(False)
            table.resizeColumnsToContents()
                
        except Exception as e:
            Logger.log_error(f"Ошибка при настройке таблицы сопоставлений: {str(e)}")

    def _create_table_row(self, table, row_idx, dxf_entity, db_handle_map, db_entities, mappings):
        """Создание одной строки в таблице сопоставлений"""
        # Текст сущности
        dxf_text = f"{dxf_entity['type']}(#{dxf_entity['handle']})"
        dxf_item = QtWidgets.QTableWidgetItem(dxf_text)
        dxf_item.setFlags(dxf_item.flags() & ~Qt.ItemIsEditable)
        
        if dxf_entity['handle'] not in db_handle_map:
            dxf_item.setBackground(Qt.yellow)
            dxf_item.setToolTip("Новая сущность, отсутствующая в базе данных")
        
        table.setItem(row_idx, 0, dxf_item)
        
        # Комбобокс для сущности БД
        combo = QtWidgets.QComboBox()
        combo.addItem('')
        for db_entity in db_entities:
            display_text = f"{db_entity['type']}(#{db_entity['handle']})"
            combo.addItem(display_text, db_entity['id'])
        
        if dxf_entity['handle'] in db_handle_map:
            db_entity = db_handle_map[dxf_entity['handle']]
            display_text = f"{db_entity['type']}(#{db_entity['handle']})"
            index = combo.findText(display_text)
            if index >= 0:
                combo.setCurrentIndex(index)
                mappings[dxf_entity['handle']] = {
                    'entity_id': db_entity['id'],
                    'attributes': {}
                }
        
        table.setCellWidget(row_idx, 1, combo)
        
        # Кнопка атрибутов
        attr_button = QPushButton("Показать атрибуты")
        attr_button.clicked.connect(
            lambda checked, e=dxf_entity, d=db_handle_map.get(dxf_entity['handle']):
                self._show_attributes_dialog(e, d)
        )
        table.setCellWidget(row_idx, 2, attr_button)
        
        # Подключаем сигнал комбобокса
        combo.currentIndexChanged.connect(
            lambda idx, h=dxf_entity['handle'], c=combo: 
                self.on_entity_mapping_changed(h, c.currentData(), mappings)
        )

    def on_ok_clicked(self):
        """Обработка нажатия кнопки OK"""
        add_connection(self.dbname, self.username, self.password)
        
        file_name = self.new_file_name.text().strip() if self.is_new_file else None
        if self.is_new_file and not file_name:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please enter a file name")
            return

        # Добавляем информацию о таблице                
        table_info = {
            'is_new_file': self.is_new_file,
            'file_id': self.selected_file_id,
            'layer_id': self.selected_layer_id,
            'new_file_name': file_name,
            'import_mode': self.import_mode,
            'geom_mappings': self.geom_mappings if not self.is_new_file and self.import_mode == 'mapping' else None,
            'nongeom_mappings': self.nongeom_mappings if not self.is_new_file and self.import_mode == 'mapping' else None
        }
        
        export_dxf(
            self.username,
            self.password,                
            self.address,                   
            self.port,                  
            self.dbname,
            self.dxf_handler,
            table_info
        )
        self.accept()

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

    def _show_attributes_dialog(self, dxf_entity, db_entity):
        """Показать атрибуты в отдельном диалоговом окне"""
        from .attribute_dialog import AttributeDialog
        dialog = AttributeDialog(dxf_entity, db_entity, self)
        if dialog.exec_() == QDialog.Accepted:
            # Получаем сопоставленные атрибуты из диалогового окна
            if db_entity and 'handle' in db_entity:
                # Обновляем сопоставления на основе результатов диалога
                handle = dxf_entity['handle']
                if handle in self.geom_mappings:
                    self.geom_mappings[handle]['attributes'] = dialog.get_mapped_attributes()
                elif handle in self.nongeom_mappings:
                    self.nongeom_mappings[handle]['attributes'] = dialog.get_mapped_attributes()

    def on_entity_mapping_changed(self, dxf_handle, db_id, mappings):
        """Обновление сопоставления при изменении выбора объекта"""
        if db_id:
            mappings[dxf_handle] = {
                'entity_id': db_id,
                'attributes': {}  # Сбрасываем сопоставление атрибутов
            }
        else:
            mappings.pop(dxf_handle, None)

