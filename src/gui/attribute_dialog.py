from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QHeaderView, QDialogButtonBox

from ..localization.localization_manager import LocalizationManager

class AttributeDialog(QDialog):
    def __init__(self, dxf_entity, db_entity, parent=None):
        super().__init__(parent)
        self.lm = LocalizationManager.instance()  # Инициализация менеджера локализации
        self.setWindowTitle(self.lm.get_string("ATTRIBUTE_DIALOG", "title"))
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Создание таблицы атрибутов
        self.attr_table = QTableWidget()
        self.attr_table.setColumnCount(3)  # Добавлен столбец для флажка сопоставления
        self.attr_table.setHorizontalHeaderLabels([
            self.lm.get_string("ATTRIBUTE_DIALOG", "map_column"),
            self.lm.get_string("ATTRIBUTE_DIALOG", "dxf_attr_column"),
            self.lm.get_string("ATTRIBUTE_DIALOG", "db_attr_column")
        ])
        self.attr_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Получение атрибутов DXF из иерархии объекта
        self.dxf_attrs = {}
        if hasattr(dxf_entity['entity'], 'dxf'):
            for key in dxf_entity['entity'].dxf.all_existing_dxf_attribs():
                try:
                    value = getattr(dxf_entity['entity'].dxf, key)
                    self.dxf_attrs[key] = str(value)
                except:
                    continue
                    
        # Получение атрибутов БД из иерархии extra_data
        self.db_attrs = {}
        if db_entity and 'extra_data' in db_entity:
            if 'attributes' in db_entity['extra_data']:
                self.db_attrs = db_entity['extra_data']['attributes']
        
        # Заполнение таблицы
        all_attrs = set(list(self.dxf_attrs.keys()) + list(self.db_attrs.keys()))
        self.attr_table.setRowCount(len(all_attrs))
        
        for i, attr in enumerate(sorted(all_attrs)):
            # Флажок для сопоставления
            checkbox = QtWidgets.QCheckBox()
            checkbox_widget = QtWidgets.QWidget()
            checkbox_layout = QtWidgets.QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            
            # Значение DXF
            dxf_value = self.dxf_attrs.get(attr, '')
            dxf_item = QtWidgets.QTableWidgetItem(f"{attr}: {dxf_value}")
            dxf_item.setFlags(dxf_item.flags() & ~Qt.ItemIsEditable)
            
            # Значение БД
            db_value = self.db_attrs.get(attr, '')
            db_item = QtWidgets.QTableWidgetItem(f"{attr}: {db_value}")
            db_item.setFlags(db_item.flags() & ~Qt.ItemIsEditable)
            
            # Подсветка различий и установка флажка, если значения отличаются
            if str(dxf_value) != str(db_value):
                dxf_item.setBackground(Qt.yellow)
                db_item.setBackground(Qt.yellow)
                checkbox.setChecked(True)
            
            self.attr_table.setCellWidget(i, 0, checkbox_widget)
            self.attr_table.setItem(i, 1, dxf_item)
            self.attr_table.setItem(i, 2, db_item)
        
        layout.addWidget(self.attr_table)
        
        # Добавление кнопок ОК/Отмена
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.Ok).setText(self.lm.get_string("COMMON", "ok"))
        button_box.button(QDialogButtonBox.Cancel).setText(self.lm.get_string("COMMON", "cancel"))
        layout.addWidget(button_box)

    def get_mapped_attributes(self):
        """Возвращает словарь сопоставленных атрибутов"""
        mapped_attrs = {}
        for row in range(self.attr_table.rowCount()):
            checkbox = self.attr_table.cellWidget(row, 0).findChild(QtWidgets.QCheckBox)
            if checkbox and checkbox.isChecked():
                dxf_item = self.attr_table.item(row, 1)
                attr_name = dxf_item.text().split(":")[0].strip()
                mapped_attrs[attr_name] = self.dxf_attrs.get(attr_name)
        return mapped_attrs
