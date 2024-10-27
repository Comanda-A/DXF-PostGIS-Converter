
from PyQt5 import QtWidgets
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from PyQt5.QtWidgets import QTreeWidgetItem, QHeaderView
import os

from ..db.saved_connections_manager import *
from ..plugins.db_manager.db_plugins.plugin import DBPlugin
from ..tree_widget_handler import TreeWidgetHandler
from ..logger.logger import Logger
from ..db.database import export_dxf
from ..dxf.dxf_handler import DXFHandler


# Load UI file for PyQt
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'export_dialog.ui'))

class ExportDialog(QtWidgets.QDialog, FORM_CLASS):

    def __init__(self, dxf_tree_widget_handler: TreeWidgetHandler, dxf_handler: DXFHandler, parent=None):
        """Constructor."""
        super(ExportDialog, self).__init__(parent)
        self.setupUi(self)
        self.dlg = None
        self.dxf_tree_widget_handler = dxf_tree_widget_handler
        self.dxf_handler = dxf_handler

        self.address = 'none'
        self.port = '5432'
        self.dbname = 'none'
        self.username = 'none'
        self.password = 'none'
        self.schemaname = 'none'

        self.select_db_button.clicked.connect(self.on_select_db_button_clicked)

        self.port_lineedit.textChanged.connect(self.on_port_changed)
        self.password_lineedit.textChanged.connect(self.on_password_changed)

        # Подписываемся на сигналы кнопок
        self.buttonBox.accepted.connect(self.on_ok_clicked)
        self.buttonBox.rejected.connect(self.on_cancel_clicked)
        
        # Set the stretch factors for the columns
        self.tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree_widget.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        self.refresh_data_dialog()


    def on_port_changed(self, text):
        self.port = text


    def on_password_changed(self, text):
        self.password = text


    def copy_checked_items(self, parent_item, new_parent_item):
        '''
        Рекурсивная функция для копирования всех отмеченных (Checked) дочерних элементов из дерева.

        parent_item: исходный элемент (например, файл или слой) из первого дерева.
        new_parent_item: соответствующий элемент в новом дереве, куда копируются отмеченные элементы.
        '''
        # Проходим по всем дочерним элементам
        for i in range(parent_item.childCount()):
            child_item = parent_item.child(i)

            # Если элемент отмечен
            if child_item.checkState(0) == Qt.Checked:
                # Копируем элемент в новое дерево
                new_child_item = QTreeWidgetItem([child_item.text(0)])
                new_parent_item.addChild(new_child_item)

                # Рекурсивно копируем его дочерние элементы
                self.copy_checked_items(child_item, new_child_item)


    def populate_tree_widget(self):
        
        # Очищаем tree_widget перед заполнением
        self.tree_widget.clear()

        # Проходим по всем элементам первого дерева
        top_level_count = self.dxf_tree_widget_handler.tree_widget.topLevelItemCount()

        for i in range(top_level_count):
            file_item = self.dxf_tree_widget_handler.tree_widget.topLevelItem(i)

            # Проверяем, отмечен ли файл
            if file_item.checkState(0) == Qt.Checked:
                # Копируем файл в новое дерево
                new_file_item = QTreeWidgetItem([file_item.text(0)])
                self.tree_widget.addTopLevelItem(new_file_item)

                self.copy_checked_items(file_item, new_file_item)


    def refresh_data_dialog(self):
        self.populate_tree_widget()
        self.address_label.setText(self.address)
        self.port_lineedit.setText(self.port)
        self.dbname_label.setText(self.dbname)
        self.schema_label.setText(self.schemaname)
        self.username_label.setText(self.username)
        self.password_lineedit.setText(self.password)
        self.show_window()


    def show_window(self):
        # Показать окно и сделать его активным
        self.raise_()
        self.activateWindow()
        self.show()


    def on_select_db_button_clicked(self):
        from .providers_dialog import ProvidersDialog

        if self.dlg is None:
            self.dlg = ProvidersDialog()
            self.dlg.show()
            result = self.dlg.exec_()

            if result and self.dlg.db_tree.currentSchema() is not None:
                self.address = self.dlg.db_tree.currentDatabase().connection().db.connector.host
                self.dbname = self.dlg.db_tree.currentDatabase().connection().db.connector.dbname
                self.username = self.dlg.db_tree.currentDatabase().connection().db.connector.user
                self.schemaname = self.dlg.db_tree.currentSchema().name
                conn = get_connection(self.dbname)
                self.password = conn['password'] if conn is not None else self.password

            self.refresh_data_dialog()

    def on_ok_clicked(self):
        add_connection(self.dbname, self.username, self.password, self.address, self.port)
        #try:
        export_dxf(
            self.username,
            self.password,                
            self.address,                   
            self.port,                  
            self.dbname,
            self.dxf_handler
        )
        self.accept()
        #except Exception as e:
        #Logger.log_error(str(e))

    def on_cancel_clicked(self):
        self.reject()
