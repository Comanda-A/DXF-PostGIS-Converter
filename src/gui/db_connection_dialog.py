import os
from PyQt5 import QtWidgets, QtCore
from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import QFileDialog, QProgressDialog
from qgis.PyQt.QtCore import Qt

from ..db.saved_connections_manager import add_connection


# Load UI file for PyQt
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'db_connection_dialog.ui'))


class DBConnectionDialog(QtWidgets.QDialog, FORM_CLASS):

    def __init__(self, connection_name, parent=None):
        """Constructor."""
        super(DBConnectionDialog, self).__init__(parent)
        self.setupUi(self)
        self.connection_name = connection_name
        self.saveButton.clicked.connect(self.save_button)
        self.show_dialog()
    

    def show_dialog(self):
        ''' Show the dialog '''
        self.show()
        # Run the dialog event loop
        result = self.exec_()
        # See if OK was pressed
        if result:
            pass


    def save_button(self):
        add_connection(
            self.connection_name,
            self.userLineEdit.text(),
            self.passwordLineEdit.text(),
        )
        self.accept()
        