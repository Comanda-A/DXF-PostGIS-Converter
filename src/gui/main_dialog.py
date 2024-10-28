import os
import asyncio

from qgis.PyQt import uic, QtWidgets, QtCore
from qgis.PyQt.QtWidgets import QMessageBox, QProgressDialog, QTreeWidgetItem, QPushButton, QWidget, QHBoxLayout, QHeaderView, QFileDialog
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProviderRegistry, QgsDataSourceUri
from functools import partial


from ..logger.logger import Logger
from ..db.saved_connections_manager import get_all_connections, get_connection, edit_connection_via_dialog
from ..dxf.dxf_handler import DXFHandler
from ..tree_widget_handler import TreeWidgetHandler
from ..db.database import get_all_files_from_db, import_dxf


# Load UI file for PyQt
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'main_dialog.ui'))


class ConverterDialog(QtWidgets.QDialog, FORM_CLASS):
    """
    Dialog class for the DXF to DB converter plugin.
    """

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(ConverterDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface

        self.dxf_handler = DXFHandler(self.type_shape, self.type_selection)
        self.dxf_tree_widget_handler = TreeWidgetHandler(self.dxf_tree_widget)
        self.db_tree_widget_handler = TreeWidgetHandler(self.db_structure_treewidget)

        # нажатие по кнопке export_to_db_button
        self.export_to_db_button.clicked.connect(self.export_to_db_button_click)

        # нажатие по другой вкладке tabWidget
        self.tabWidget.currentChanged.connect(self.handle_tab_change)

    def handle_tab_change(self, index):
        # 0 - dxf-postgis, 1 - postgis - dxf, 2 - setting
        if index == 1:
            self.refresh_db_structure_treewidget()

    def refresh_settings_databases_combobox(self):
        ''' Обновление содержимого combobox в settings_databases_combobox '''
        db_names = get_all_connections().keys()
        self.settings_databases_combobox.clear()
        self.settings_databases_combobox.addItems(db_names)

    def connect_to_db_button(self):
        db_name = self.settings_databases_combobox.currentText()
        connection = get_connection(db_name)
        if connection is not None:
            Logger.log_warning('пока что не работает')
        else:
            Logger.log_warning('Database is unselected!')

    async def read_dxf(self, file_name):
        """
        Handle DXF file selection and populate tree widget with layers and entities.
        """
        self.label.setText(os.path.basename(file_name))
        await self.start_long_task("read_dxf_file", self.dxf_handler.read_dxf_file, self.dxf_handler, file_name)

    async def read_multiple_dxf(self, file_names):
        """
        Handle multiple DXF file selections and populate tree widget with layers and entities.
        """
        total_files = len(file_names)
        self.progress_dialog = QProgressDialog("Processing...", "Cancel", 0, total_files, self)
        self.progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        self.progress_dialog.show()

        tasks = [self.read_dxf(file_name) for file_name in file_names]
        await asyncio.gather(*tasks)

    async def start_long_task(self, task_id, func, real_func, *args):
        """
        Starts a long task by creating a progress dialog and connecting it to a worker handler.
        Args:
            task_id (str): The identifier of the task.
            func (callable): The function to be executed.
            real_func (callable): The function to be executed in the worker.
            *args: Variable length argument list.
        """

        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, func, *args)
        result = await future

        self.on_finished(task_id, result)

    def on_finished(self, task_id, result):
        """
        Handles the completion of a task by stopping the worker.
        """
        if result is not None:
            if task_id == "read_dxf_file":
                self.dxf_tree_widget_handler.populate_tree_widget(result)
            elif task_id == "select_entities_in_area":
                self.dxf_tree_widget_handler.select_area(result)

        self.export_to_db_button.setEnabled(self.dxf_handler.file_is_open)
        self.select_area_button.setEnabled(self.dxf_handler.file_is_open)
        self.progress_dialog.close()

    def refresh_dfx_tree_widget(self):
        if self.dxf_handler.file_is_open:
            self.dxf_tree_widget_handler.populate_tree_widget(self.dxf_handler.get_layers())
        else:
            self.dxf_tree_widget_handler.populate_tree_widget({})

        self.select_area_button.setEnabled(self.dxf_handler.file_is_open)
        self.export_to_db_button.setEnabled(self.dxf_handler.file_is_open)


    def export_to_db_button_click(self):
        from .export_dialog import ExportDialog

        dlg = ExportDialog(self.dxf_tree_widget_handler, self.dxf_handler)
        dlg.show()
        result = dlg.exec_()         

        # See if OK was pressed
        if result:
            pass
        
        self.show_window()


    def show_window(self):
        # Показать окно и сделать его активным
        self.raise_()
        self.activateWindow()
        self.show()


    def refresh_db_structure_treewidget(self):
        self.db_structure_treewidget.clear()
        # Получаем список всех зарегистрированных подключений PostGIS
        settings = QgsProviderRegistry.instance().providerMetadata('postgres').connections()

        for conn_name, conn_metadata in settings.items():
            uri = QgsDataSourceUri(conn_metadata.uri())
            conn_item = QTreeWidgetItem([conn_name])
            self.db_structure_treewidget.addTopLevelItem(conn_item)

            info_button = QPushButton('info') # Создаем кнопку
            info_button.setFixedSize(80, 20)
            info_button.clicked.connect(
                partial(self.open_db_info_dialog, conn_name, uri.database(), uri.host(), uri.port()))
            widget = QWidget() # Создаем контейнер для кнопки
            layout = QHBoxLayout(widget)
            layout.addWidget(info_button)
            layout.setAlignment(Qt.AlignLeft)
            layout.setContentsMargins(0, 0, 0, 0)
            widget.setLayout(layout)
            self.db_structure_treewidget.setItemWidget(conn_item, 1, widget) # Добавляем кнопку в соответствующую колонку узла дерева
            
            self.db_structure_treewidget.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            self.db_structure_treewidget.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            
            conn = get_connection(conn_name) or {}
            username = conn.get('username', 'N/A')
            password = conn.get('password', 'N/A')
            files = get_all_files_from_db(username, password, uri.host(), uri.port(), uri.database())
            
            if files is None:
                conn_item.setText(0, f'{conn_name} (Error when receiving data)')
            else:
                for file in files:
                    entity_description = f"{file['filename']}"
                    entity_item = QTreeWidgetItem([entity_description])
                    conn_item.addChild(entity_item)

                    info_button = QPushButton('import') # Создаем кнопку
                    info_button.setFixedSize(80, 20)
                    info_button.clicked.connect(
                        partial(self.import_from_db_button_click, conn_name, uri.database(), uri.host(), uri.port(), file['filename'], file['id']))
                    widget = QWidget() # Создаем контейнер для кнопки
                    layout = QHBoxLayout(widget)
                    layout.addWidget(info_button)
                    layout.setAlignment(Qt.AlignLeft)
                    layout.setContentsMargins(20, 0, 0, 0)
                    widget.setLayout(layout)
                    self.db_structure_treewidget.setItemWidget(entity_item, 1, widget) # Добавляем кнопку в соответствующую колонку узла дерева


    def open_db_info_dialog(self, conn_name, dbname, host, port):
        # Получаем данные о подключении
        conn = get_connection(conn_name) or {}
        username = conn.get('username', 'N/A')
        password = conn.get('password', 'N/A')

        # Формируем текст для отображения
        info_text = (
            f"Connection: {conn_name}\n"
            f"Database: {dbname}\n"
            f"Username: {username}\n"
            f"Password: {password}\n"
            f"Host: {host}\n"
            f"Port: {port}"
        )

        # Создаем диалоговое окно
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Database Connection Info")
        msg_box.setText(info_text)

        # Добавляем кнопки
        edit_button = msg_box.addButton("Edit", QMessageBox.ActionRole)
        ok_button = msg_box.addButton(QMessageBox.Ok)

        # Отображаем диалоговое окно
        msg_box.exec_()

        # Проверяем, какую кнопку нажали
        if msg_box.clickedButton() == edit_button:
            edit_connection_via_dialog(conn_name)
            self.refresh_db_structure_treewidget()
            self.open_db_info_dialog(conn_name, dbname, host, port)


    def import_from_db_button_click(self, conn_name, dbname, host, port, file_name, file_id):
        # Открываем диалоговое окно для выбора пути сохранения файла
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(None, "Save file as", "", "Все файлы (*)", options=options)
        
        conn = get_connection(conn_name) or {}
        username = conn.get('username', 'N/A')
        password = conn.get('password', 'N/A')

        if file_path:
            import_dxf(username, password, host, port, dbname, file_id, file_path)
        else:
            QMessageBox.warning(None, "Error", "Please select the path to save the file.")



'''

    uri = QgsDataSourceUri(conn_metadata.uri())
            connection_info = {
                'name': conn_name,
                'host': uri.host(),
                'port': uri.port(),
                'database': uri.database(),
                'username': uri.username(),
                'password': uri.password(),
                'schema': uri.schema(),
                'table': uri.table()
            }
            Logger.log_message(str(connection_info))
        self.pushButton.clicked.connect(self.select_dxf_button)
        self.treeWidget.itemChanged.connect(self.handle_item_changed)
        self.importButton.clicked.connect(self.push)
        self.settings_editButton.clicked.connect(self.edit_connections_button)
        self.settings_editButton_2.clicked.connect(self.edit_table_name_button)
        #self.settings_editButton_2.enabled.
        self.settings_connectButton.clicked.connect(self.select_dbcombobox)
        self.settings_dbComboBox.currentIndexChanged.connect(self.select_dbcombobox)
        self.settings_tbComboBox.currentIndexChanged.connect(self.select_tbcombobox)
        event_db_connection_changed.append(self.update_dbcombobox)
        event_db_connection_changed.append(self.update_tbcombobox)
        self.initialize_combobox()

        self.truncateCheckBox.stateChanged.connect(self.on_truncate_checked)
        self.onlyMappingCheckBox.stateChanged.connect(self.on_onlyMapping_checked)

        self.dxf_handler = DXFHandler(self.type_shape, self.type_selection)
        Logger.log_message(f'{self.type_shape.currentText()}, {self.type_selection.currentText()}')
        self.tree_widget_handler = TreeWidgetHandler(self.treeWidget)
        self.worker_handler = WorkerHandler()
        self.progress_dialog = None
    #TODO: отсюда взять
    async def read_dxf(self, file_name):
        """
        Handle DXF file selection and populate tree widget with layers and entities.
        """
        self.label.setText(os.path.basename(file_name))
        await self.start_long_task("read_dxf_file", self.dxf_handler.read_dxf_file, self.dxf_handler, file_name)
    async def read_multiple_dxf(self, file_names):
        """
        Handle multiple DXF file selections and populate tree widget with layers and entities.
        """
        total_files = len(file_names)
        self.progress_dialog = QProgressDialog("Processing...", "Cancel", 0, total_files, self)
        self.progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        self.progress_dialog.show()

        tasks = [self.read_dxf(file_name) for file_name in file_names]
        await asyncio.gather(*tasks)


    async def start_long_task(self, task_id, func, real_func,  *args):
        """
        Starts a long task by creating a progress dialog and connecting it to a worker handler.
        Args:
            task_id (str): The identifier of the task.
            func (callable): The function to be executed.
            real_func (callable): The function to be executed in the worker.
            *args: Variable length argument list.
        """

        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, func, *args)
        result = await future

        self.on_finished(task_id, result)
        #self.worker_handler.start_worker(func, self.on_finished, self.progress_dialog.setValue, real_func, task_id, *args)

    def on_finished(self, task_id, result):
        """
        Handles the completion of a task by stopping the worker.
        """
        self.worker_handler.stop_worker()
        if result is not None:
            if task_id == "read_dxf_file":
                self.tree_widget_handler.populate_tree_widget(result)
                self.selectionButton.setEnabled(True)
            elif task_id == "select_entities_in_area":
                self.tree_widget_handler.select_area(result)
        
        self.set_selection_button_status()
        self.progress_dialog.close()

    def handle_item_changed(self, item, column):
        """
        Handle changes in item check state and propagate changes to child items.
        """
        self.tree_widget_handler.handle_item_changed(item, column)

    def set_selection_button_status(self):
        """
        Enable or disable the selection button based on whether a file is open.
        """
        self.selectionButton.setEnabled(self.dxf_handler.file_is_open)

    def connect_to_db(self, db_name, connection_data):
        """
        Connect to the database using provided credentials.
        """

        if hasattr(self, 'db_manager'):
            self.db_manager.close()

        host = connection_data['host']
        port = connection_data['port']
        database = db_name
        user = connection_data['user']
        password = connection_data['password']

        self.db_manager = DBManager(host, port, database, user, password)
        if self.db_manager.connect():
            self.settings_statusLabel.setText(f"Connected to database {db_name}")
            self.importButton.setEnabled(True)
            layerViewer = LayerSetViewer(self.db_manager, self.settings_structureTreeWidget)
            layerViewer.load_layer_sets()
        else:
            self.settings_statusLabel.setText(f"Failed to connect to database {db_name}")

    def push(self):
        """
        Push selected objects to the database.
        """
        selected_objects = {}
        for layer, data in self.tree_widget_handler.tree_items.items():
            if data['item'].checkState(0) == Qt.Checked:
                for entity_description, entity_item in data['entities'].items():
                    if entity_item.checkState(0) == Qt.Checked:
                        attributes = []
                        geometry = []
                        for i in range(entity_item.childCount()):
                            child = entity_item.child(i)
                            if child.text(0) == 'Атрибуты':
                                attributes = [attr.text(0) for attr in self.tree_widget_handler.get_checked_children(child)]
                            elif child.text(0) == 'Геометрия':
                                geometry = [geom.text(0) for geom in self.tree_widget_handler.get_checked_children(child)]

                        if layer not in selected_objects:
                            selected_objects[layer] = []

                        selected_objects[layer].append({
                            'entity_description': entity_item.text(0),
                            'attributes': attributes,
                            'geometry': geometry
                        })

        if selected_objects:
            layers = []
            for layer_name, entities in selected_objects.items():
                json_data = json.dumps(entities)
                layers.append({
                    'layer_name': layer_name,
                    'json_data': json_data
                })
            self.db_manager.save_layer_set(
                "Example Layer Set", 
                "This is an example layer set.", 
                layers,
                self.table_name, 
                self.truncateCheckBox.isChecked(),
                self.onlyMappingCheckBox.isChecked(),
                self.logCheckBox.isChecked())
            Logger.log_message("Push")
    
    def update_tbcombobox(self):
        db_names = get_all_table_name_in_current_db(self.db_name)
        self.settings_tbComboBox.clear()
        self.settings_tbComboBox.addItems(db_names)

    def select_tbcombobox(self, index):
        if index >= 0:
            db_table_name = self.settings_tbComboBox.itemText(index)
            name = get_table_name_in_current_db(self.db_name, db_table_name)
            self.table_name = name
            # Сохраняем индекс таблицы
            settings = QtCore.QSettings()
            settings.setValue('converter_dialog/tb_index', index)

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.FocusIn and source is self.settings_dbComboBox:
            self.update_dbcombobox()
        return super(ConverterDialog, self).eventFilter(source, event)
    
    def edit_connections_button(self):
        self.edit_dialog = EditConnectionsDialog()
        self.edit_dialog.show()
        result = self.edit_dialog.exec_()
    
    def edit_table_name_button(self):
        self.edit_dialog = EditTableNameDialog(self.db_name)
        self.edit_dialog.show()
        result = self.edit_dialog.exec_()
   
    def initialize_combobox(self):
        # Инициализация сохранённых индексов
        settings = QtCore.QSettings()
        try:
            db_index = int(settings.value('converter_dialog/db_index', 0))
            tb_index = int(settings.value('converter_dialog/tb_index', 0))
        except:
            Logger.log_message(f"Error load data")
            settings.remove('converter_dialog/db_index')
            settings.remove('converter_dialog/tb_index')
            db_index = 0
            tb_index = 0
            
        self.update_dbcombobox()

        # Установка индексов в ComboBox
        self.settings_dbComboBox.setCurrentIndex(db_index)

        # Инициализация db_name и table_name значениями из ComboBox
        if self.settings_dbComboBox.count() > 0:
            self.db_name = self.settings_dbComboBox.itemText(db_index)
        else:
            self.db_name = "None"

        self.update_tbcombobox()  # обновляем таблицы в соответствии с выбранной базой данных
        self.settings_tbComboBox.setCurrentIndex(tb_index)

        if self.settings_tbComboBox.count() > 0:
            self.table_name = self.settings_tbComboBox.itemText(tb_index)
        else:
            self.table_name = "layers"


        Logger.log_message(f"Initialized db_name: {self.db_name}, table_name: {self.table_name}")

    def on_truncate_checked(self, state):
        if state == Qt.Checked:
            self.onlyMappingCheckBox.setChecked(False)

    def on_onlyMapping_checked(self, state):
        if state == Qt.Checked:
            self.truncateCheckBox.setChecked(False)
    
    #TODO: зародыш явного маппирования, но тогда нужно структуру записи в бд менять
    def show_field_mapping_dialog(self, layer_fields, table_columns):
        dialog = FieldMappingDialog(layer_fields, table_columns)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_mapping()
        return None
        
'''

