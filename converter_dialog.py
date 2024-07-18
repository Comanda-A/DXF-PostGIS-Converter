import os
from PyQt5 import QtWidgets, QtCore
from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import QFileDialog, QProgressDialog
from qgis.PyQt.QtCore import Qt
from .db_manager import DBManager
from .logger import Logger
from .dxf_handler import DXFHandler
from .tree_widget_handler import TreeWidgetHandler
from .worker_handler import WorkerHandler
from .connection_data_dialog import ConnectionDataDialog
from .connection_data_manager import get_all_db_names, get_connection, event_db_connection_changed

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
        self.selectionButton.clicked.connect(self.push)
        self.settings_newConnectionButton.clicked.connect(self.new_connection_button)
        self.settings_dbComboBox.currentIndexChanged.connect(self.select_dbcombobox)
        event_db_connection_changed.append(self.update_dbcombobox)

        self.update_dbcombobox()

        self.dxf_handler = DXFHandler()
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

    def connect_to_db(self):
        """
        Connect to the database using provided credentials.
        """
        host = self.hostLineEdit.text()
        port = self.portLineEdit.text()
        database = self.databaseLineEdit.text()
        user = self.userLineEdit.text()
        password = self.passwordLineEdit.text()

        self.db_manager = DBManager(host, port, database, user, password)
        if self.db_manager.connect():
            self.statusLabel.setText("Connected to database")
            self.push()
        else:
            self.statusLabel.setText("Failed to connect to database")

    def push(self):
        """
        Push selected objects to the database.
        """
        selected_objects = []
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

                        selected_objects.append({
                            'layer': layer,
                            'entities': entity_item.text(0),
                            'attributes': attributes,
                            'geometry': geometry
                        })

        if selected_objects:
            self.db_manager.save_selected_objects(selected_objects)
            Logger.log_message("Push")

    def new_connection_button(self):
        self.connection_dialog = ConnectionDataDialog()
        self.connection_dialog.show()
        result = self.connection_dialog.exec_()
        
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass

    def update_dbcombobox(self):
        db_names = get_all_db_names()
        self.settings_dbComboBox.clear()
        self.settings_dbComboBox.addItems(db_names)

    def select_dbcombobox(self, index):
        if index >= 0:
            db_name = self.settings_dbComboBox.itemText(index)
            Logger.log_message(str(db_name))
            connection = get_connection(db_name)
            #self.settings_dbComboBox.setCurrentIndex(index)
            print(f"Connecting to {db_name} with details: {connection}")

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.FocusIn and source is self.settings_dbComboBox:
            self.update_dbcombobox()
        return super(ConverterDialog, self).eventFilter(source, event)