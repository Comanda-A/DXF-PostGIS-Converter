import os
from PyQt5 import QtWidgets, QtCore
from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import QFileDialog, QProgressDialog
from qgis.PyQt.QtCore import Qt
from ..db.db_manager import DBManager
from ..logger.logger import Logger
from ..dxf.dxf_handler import DXFHandler
from ..tree_widget_handler import TreeWidgetHandler
from src.worker import WorkerHandler
from ..db.saved_connections_manager import save_table_name_in_current_db

# Load UI file for PyQt
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'table_name_dialog.ui'))

class TableNameDialog(QtWidgets.QDialog, FORM_CLASS):

    def __init__(self, db_name, parent=None):
        """Constructor."""
        super(TableNameDialog, self).__init__(parent)
        self.setupUi(self)
        self.saveButton.clicked.connect(self.save_button)
        self.name = db_name
        
    
    def save_button(self):
        save_table_name_in_current_db(self.name, self.tableNameEdit.text())

        self.accept()

        
        