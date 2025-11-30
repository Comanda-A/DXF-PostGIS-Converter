# -*- coding: utf-8 -*-
"""
Диалог для выбора места импорта DXF файлов из базы данных
"""

from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QRadioButton, QButtonGroup
from qgis.PyQt.QtCore import Qt
from ..localization.localization_manager import LocalizationManager


class ImportDestinationDialog(QDialog):
    """
    Диалог для выбора места импорта: в QGIS или в файл на ПК
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lm = LocalizationManager.instance()
        self.selected_destination = None
        
        self.setWindowTitle("Выбор места")
        
        self.setupUI()
        
        # Центрируем диалог
        if parent:
            parent_geometry = parent.geometry()
            self.move(
                parent_geometry.x() + (parent_geometry.width() - self.width()) // 2,
                parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
            )
    
    def setupUI(self):
        """Создание интерфейса диалога"""
        layout = QVBoxLayout()
        
        # Заголовок
        title_label = QLabel("Выберите, куда экспортировать DXF файл:")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Группа радиокнопок
        self.button_group = QButtonGroup()
        
        # Кнопка для импорта в QGIS
        self.qgis_radio = QRadioButton("Экспортировать в проект QGIS")
        self.qgis_radio.setChecked(True)  # По умолчанию выбран QGIS
        self.button_group.addButton(self.qgis_radio, 0)
        layout.addWidget(self.qgis_radio)
        
        # Кнопка для сохранения в файл
        self.file_radio = QRadioButton("Сохранить как файл на компьютере")
        self.button_group.addButton(self.file_radio, 1)
        layout.addWidget(self.file_radio)
        
        # Отступ
        layout.addStretch()
        
        # Кнопки OK и Cancel
        button_layout = QHBoxLayout()
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)
        
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def accept(self):
        """Обработка нажатия OK"""
        if self.qgis_radio.isChecked():
            self.selected_destination = "qgis"
        else:
            self.selected_destination = "file"
        super().accept()
    
    def get_selected_destination(self):
        """Возвращает выбранный способ импорта"""
        return self.selected_destination
