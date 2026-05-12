# -*- coding: utf-8 -*-
"""
Диалог для выбора места экспорта DXF файлов из базы данных
"""

from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QRadioButton, QButtonGroup
from qgis.PyQt.QtCore import Qt


class ExportDialog(QDialog):
    """
    Диалог для выбора места экспорта: в QGIS или в файл на ПК
    """

    def __init__(self, parent=None):
        super().__init__(parent)
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

        # Выбор источника экспорта
        source_label = QLabel("Выберите источник экспорта (как формировать файл):")
        source_label.setStyleSheet("font-weight: bold; font-size: 11px; margin-top: 5px;")
        layout.addWidget(source_label)

        self.source_group = QButtonGroup()
        
        self.source_blob_radio = QRadioButton("Как бинарный файл (созданный файл из выбранных объектов, при последнем импорте)")
        self.source_blob_radio.setChecked(True)
        self.source_group.addButton(self.source_blob_radio, 0)
        layout.addWidget(self.source_blob_radio)

        self.source_table_radio = QRadioButton("Объекты из таблиц-слоев (реконструкция DXF из таблиц, созданных при последнем импорте)")
        self.source_group.addButton(self.source_table_radio, 1)
        layout.addWidget(self.source_table_radio)

        # Выбор места назначения
        title_label = QLabel("Выберите, куда экспортировать DXF файл:")
        title_label.setStyleSheet("font-weight: bold; font-size: 11px; margin-top: 15px;")
        layout.addWidget(title_label)

        # Группа радиокнопок
        self.button_group = QButtonGroup()

        # Кнопка для экспорта в QGIS
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
        # Определяем source_mode: "tables" (из таблиц-через `extra_data`) или "blob" (оригинальный)
        self.source_mode = "tables" if self.source_table_radio.isChecked() else "blob"

        if self.qgis_radio.isChecked():
            self.selected_destination = "qgis"
        else:
            self.selected_destination = "file"
        super().accept()

    def get_selected_destination(self):
        """Возвращает выбранный способ экспорта"""
        return self.selected_destination

    def get_source_mode(self):
        """Возвращает выбранный источник (из файла или из таблиц)"""
        return getattr(self, "source_mode", "blob")
