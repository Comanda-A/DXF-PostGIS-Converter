
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QListWidgetItem
from qgis.PyQt import uic
import os

from .db_connection_dialog import DBConnectionDialog
from ..db.saved_databases_manager import get_all_connections, delete_connection, event_db_connections_edited
from ..logger.logger import Logger


# Load UI file for PyQt
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'saved_databases_dialog.ui'))

class SavedDatabasesDialog(QtWidgets.QDialog, FORM_CLASS):

    def __init__(self, parent=None):
        """Constructor."""
        super(SavedDatabasesDialog, self).__init__(parent)
        self.setupUi(self)

        self.add_button = None
        event_db_connections_edited.append(self.refresh_content)

        self.refresh_content()
        self.show_dialog()
        

    def show_dialog(self):
        ''' Show the dialog '''
        self.show()
        # Run the dialog event loop
        result = self.exec_()
        # See if OK was pressed
        if result:
            event_db_connections_edited.remove(self.refresh_content)
            


    def refresh_content(self):
        """Заполнение QListWidget доступными базами данных."""

        self.listWidget.clear()
        db_names = get_all_connections().keys()
        for index, db_name in enumerate(db_names):
            item_widget = self.create_item_widget(db_name, index)
            list_item = QListWidgetItem(self.listWidget)
            list_item.setSizeHint(item_widget.sizeHint())
            self.listWidget.addItem(list_item)
            self.listWidget.setItemWidget(list_item, item_widget)
            # Добавляем отступы между элементами
            list_item.setSizeHint(QtCore.QSize(list_item.sizeHint().width(), list_item.sizeHint().height() + 10))

        if self.add_button is None:
            # Создание кнопки добавления подключения
            self.add_button = QPushButton("+")
            self.add_button.clicked.connect(lambda : DBConnectionDialog())
                
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
        self.refresh_content()