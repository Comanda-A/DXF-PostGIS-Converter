import os
import json
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QListWidgetItem
from qgis.PyQt import uic
from .connection_data_manager import get_all_db_names, delete_connection, event_db_connection_changed
from .connection_data_dialog import ConnectionDataDialog

# Load UI file for PyQt
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'edit_connections_dialog.ui'))

class EditConnectionsDialog(QtWidgets.QDialog, FORM_CLASS):

    def __init__(self, parent=None):
        """Constructor."""
        super(EditConnectionsDialog, self).__init__(parent)
        self.setupUi(self)
        
        # Заполнение QListWidget при запуске
        self.populate_list_widget()

        # Создание кнопки добавления подключения
        self.add_button = QPushButton("+")
        self.add_button.clicked.connect(self.add_connection)
        
        # Создание лейаута для кнопки добавления
        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.add_button)
        self.button_layout.addStretch()
        self.button_layout.setContentsMargins(0, 10, 0, 10)
        
        # Добавление лейаута с кнопкой в основной лейаут
        self.main_layout = QVBoxLayout(self)
        self.main_layout.addWidget(self.listWidget)
        self.main_layout.addLayout(self.button_layout)

        # Установка нулевых отступов для основного лейаута
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        event_db_connection_changed.append(self.populate_list_widget)

    def populate_list_widget(self):
        """Заполнение QListWidget доступными базами данных."""
        self.listWidget.clear()
        db_names = get_all_db_names()
        for index, db_name in enumerate(db_names):
            item_widget = self.create_item_widget(db_name, index)
            list_item = QListWidgetItem(self.listWidget)
            list_item.setSizeHint(item_widget.sizeHint())
            self.listWidget.addItem(list_item)
            self.listWidget.setItemWidget(list_item, item_widget)
            # Добавляем отступы между элементами
            list_item.setSizeHint(QtCore.QSize(list_item.sizeHint().width(), list_item.sizeHint().height() + 10))

    def create_item_widget(self, db_name, index):
        """Создание виджета элемента списка с кнопкой удаления."""
        widget = QWidget()
        layout = QHBoxLayout()

        label = QLabel(db_name)
        button = QPushButton("Удалить")
        button.clicked.connect(lambda: self.delete_connection(db_name))

        layout.addWidget(label)
        layout.addWidget(button)
        layout.setContentsMargins(10, 0, 10, 0)
        widget.setLayout(layout)

        button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

        # Установка цвета фона для четных/нечетных элементов
        if index % 2 == 0:
            widget.setStyleSheet("background-color: #f0f0f0;")
        else:
            widget.setStyleSheet("background-color: #e6e6e6;")

        return widget

    def delete_connection(self, db_name):
        """Удаление выбранного подключения."""
        delete_connection(db_name)
        self.populate_list_widget()

    def add_connection(self):
        self.connection_dialog = ConnectionDataDialog()
        self.connection_dialog.show()
        result = self.connection_dialog.exec_()
        
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass