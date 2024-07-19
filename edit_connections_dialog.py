import os
import json
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QListWidgetItem
from qgis.PyQt import uic
from .connection_data_manager import get_all_db_names, delete_connection

# Load UI file for PyQt
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'edit_connections_dialog.ui'))

class EditConnectionsDialog(QtWidgets.QDialog, FORM_CLASS):

    def __init__(self, parent=None):
        """Constructor."""
        super(EditConnectionsDialog, self).__init__(parent)
        self.setupUi(self)
        
        # Заполнение QListWidget при запуске
        self.populate_list_widget()

    def populate_list_widget(self):
        """Заполнение QListWidget доступными базами данных."""
        self.listWidget.clear()
        db_names = get_all_db_names()
        for db_name in db_names:
            item_widget = self.create_item_widget(db_name)
            list_item = QListWidgetItem(self.listWidget)
            list_item.setSizeHint(item_widget.sizeHint())
            self.listWidget.addItem(list_item)
            self.listWidget.setItemWidget(list_item, item_widget)

    def create_item_widget(self, db_name):
        """Создание виджета элемента списка с кнопкой удаления."""
        widget = QWidget()
        layout = QHBoxLayout()

        label = QLabel(db_name)
        button = QPushButton("Удалить")
        button.clicked.connect(lambda: self.delete_connection(db_name))

        layout.addWidget(label)
        layout.addWidget(button)
        layout.setContentsMargins(0, 0, 0, 0)
        widget.setLayout(layout)

        return widget

    def delete_connection(self, db_name):
        """Удаление выбранного подключения."""
        delete_connection(db_name)
        self.populate_list_widget()
