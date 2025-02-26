from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QVBoxLayout, QPushButton, QLabel
from qgis.PyQt import uic

from ..plugins.db_manager.db_tree import DBTree
from ..localization.localization_manager import LocalizationManager
import os


# Load UI file for PyQt
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'providers_dialog.ui'))


class ProvidersDialog(QtWidgets.QDialog, FORM_CLASS):
    
    def __init__(self, parent=None):
        """Constructor."""
        super(ProvidersDialog, self).__init__(parent)
        self.setupUi(self)
        self.lm = LocalizationManager.instance()  # Инициализация менеджера локализации
        
        # Устанавливаем заголовок окна
        self.setWindowTitle(self.lm.get_string("PROVIDERS_DIALOG", "title"))

        # Создаем макет для размещения элементов
        self.layout = QVBoxLayout(self)

        # Добавляем метку вверху окна
        self.label = QLabel(self.lm.get_string("PROVIDERS_DIALOG", "label"), self)
        self.layout.addWidget(self.label)

        # Добавляем дерево для отображения баз данных
        self.db_tree = DBTree(self)
        self.db_tree.selectionModel().currentChanged.connect(self.on_item_selected)  # Подключаем метод для выбора БД
        self.layout.addWidget(self.db_tree)

        # Добавляем кнопку для обновления подключений
        self.refresh_button = QPushButton(self.lm.get_string("PROVIDERS_DIALOG", "refresh_button"), self)
        self.refresh_button.clicked.connect(lambda: self.db_tree.reconnect())
        self.layout.addWidget(self.refresh_button)

        # Добавляем кнопку "Выбрать" (по умолчанию неактивна)
        self.select_button = QPushButton(self.lm.get_string("PROVIDERS_DIALOG", "select_button"), self)
        self.select_button.setEnabled(False)
        self.select_button.clicked.connect(self.on_select_button_clicked)
        self.layout.addWidget(self.select_button)


    def on_item_selected(self, current, previous):
        self.select_button.setEnabled(self.db_tree.currentSchema() is not None)

    def on_select_button_clicked(self):
        self.accept()
