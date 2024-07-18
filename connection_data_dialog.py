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
from .connection_data_manager import save_connection


# Load UI file for PyQt
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'connection_data_dialog.ui'))

class ConnectionDataDialog(QtWidgets.QDialog, FORM_CLASS):

    def __init__(self, parent=None):
        """Constructor."""
        super(ConnectionDataDialog, self).__init__(parent)
        self.setupUi(self)
        self.saveButton.clicked.connect(self.save_button)
    
    def save_button(self):
        save_connection(
            self.databaseLineEdit.text(),
            self.userLineEdit.text(),
            self.passwordLineEdit.text(),
            self.hostLineEdit.text(),
            self.portLineEdit.text()
        )
        self.accept()
        