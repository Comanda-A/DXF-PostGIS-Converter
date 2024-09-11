import os
import json

from qgis.PyQt import uic, QtWidgets, QtCore
from qgis.PyQt.QtWidgets import QFileDialog, QProgressDialog, QLineEdit, QDialog
from qgis.PyQt.QtCore import Qt
from .db_manager import DBManager
from .logger import Logger
from .dxf_handler import DXFHandler
from .tree_widget_handler import TreeWidgetHandler
from .worker_handler import WorkerHandler
from .connection_data_dialog import ConnectionDataDialog
from .connection_data_manager import get_all_db_names, get_connection, event_db_connection_changed, get_all_table_name_in_current_db, get_table_name_in_current_db
from .edit_connections_dialog import EditConnectionsDialog
from .edit_table_name_dialog import EditTableNameDialog
from .layer_set_viewer import LayerSetViewer
from .FieldMappingDialog import FieldMappingDialog
# Load UI file for PyQt
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'dialog_base.ui'))

class ConverterDialog(QtWidgets.QDialog, FORM_CLASS):
    """
    Dialog class for the DXF to DB converter plugin.
    """

    def __init__(self, parent=None):
        """Constructor."""
        super(ConverterDialog, self).__init__(parent)
        self.setupUi(self)
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

    def select_dxf_button(self):
        """
        Handle DXF file selection and populate tree widget with layers and entities.
        """
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        file_name, _ = QFileDialog.getOpenFileName(self, "Select DXF File", "", "DXF Files (*.dxf);;All Files (*)", options=options)
        #Logger.log_message(str(file_name))
        if file_name:
            self.label.setText(os.path.basename(file_name))
            self.start_long_task("read_dxf_file", self.dxf_handler.read_dxf_file, self.dxf_handler, file_name)

    def start_long_task(self, task_id, func, real_func,  *args):
        """
        Starts a long task by creating a progress dialog and connecting it to a worker handler.
        Args:
            task_id (str): The identifier of the task.
            func (callable): The function to be executed.
            real_func (callable): The function to be executed in the worker.
            *args: Variable length argument list.
        """
        self.progress_dialog = QProgressDialog("Processing...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        self.progress_dialog.show()

        self.worker_handler.start_worker(func, self.on_finished, self.progress_dialog.setValue, real_func, task_id, *args)

        self.progress_dialog.canceled.connect(self.worker_handler.stop_worker)

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

    def update_dbcombobox(self):
        db_names = get_all_db_names()
        self.settings_dbComboBox.clear()
        self.settings_dbComboBox.addItems(db_names)

    def select_dbcombobox(self, index):
        if index >= 0:
            self.db_name = self.settings_dbComboBox.itemText(index)
            connection = get_connection(self.db_name)
            Logger.log_message(f"Connecting to {self.db_name} with details: {connection}")
            self.connect_to_db(self.db_name, connection)
            self.update_tbcombobox()
            # Сохраняем индекс в QGIS Settings
            settings = QtCore.QSettings()
            settings.setValue('converter_dialog/db_index', index)
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
        
