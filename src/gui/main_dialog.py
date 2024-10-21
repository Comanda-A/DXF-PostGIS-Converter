import os
import json
import random

from qgis.PyQt import uic, QtWidgets, QtCore
from qgis.PyQt.QtWidgets import QFileDialog, QProgressDialog, QLineEdit, QDialog
from qgis.PyQt.QtCore import Qt

from ..logger.logger import Logger
from .saved_databases_dialog import SavedDatabasesDialog
from ..db.saved_databases_manager import get_all_connections, get_connection, event_db_connections_edited
from ..db.database import connect_to_database
from ..dxf.dxf_handler import DXFHandler
from ..tree_widget_handler import TreeWidgetHandler
from ..db.database import send_layers_to_db


'''
from ..db.db_manager import DBManager
from ..logger.logger import Logger
from ..dxf.tree_widget_handler import TreeWidgetHandler
from ..worker.worker_handler import WorkerHandler
from .connection_data_dialog import ConnectionDataDialog
from ..db.connection_data_manager import get_all_db_names, get_connection, event_db_connection_changed, get_all_table_name_in_current_db, get_table_name_in_current_db
from .edit_connections_dialog import EditConnectionsDialog
from .edit_table_name_dialog import EditTableNameDialog
from ...layer_set_viewer import LayerSetViewer
from ..FieldMappingDialog import FieldMappingDialog
'''


# Load UI file for PyQt
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'main_dialog.ui'))


class ConverterDialog(QtWidgets.QDialog, FORM_CLASS):
    """
    Dialog class for the DXF to DB converter plugin.
    """

    def __init__(self, parent=None):
        """Constructor."""
        super(ConverterDialog, self).__init__(parent)
        self.setupUi(self)

        self.dxf_handler = DXFHandler()

        # нажатие по кнопке edit в settings
        self.settings_saved_db_button.clicked.connect(
            lambda : SavedDatabasesDialog()
        )

        # нажатие по кнопке connect в настройках
        self.settings_connect_db_button.clicked.connect(self.connect_to_db_button)

        # нажатие по кнопке выбора dxf файла
        self.open_dxf_button.clicked.connect(self.open_dxf_button_click)
        
        # нажатие по кнопке export_to_db_button
        self.export_to_db_button.clicked.connect(self.export_to_db_button_click)

        # событие изменения сохраненных подключений
        event_db_connections_edited.append(self.refresh_settings_databases_combobox)

        # создание TreeWidgetHandler для dxf_tree_widget
        self.dxf_tree_widget_handler = TreeWidgetHandler(self.dxf_tree_widget)

        self.refresh_settings_databases_combobox()

        # отображение окна
        self.show_dialog()
    
    
    def show_dialog(self):
        ''' Show the dialog '''
        self.show()
        # Run the dialog event loop
        result = self.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass

    
    def refresh_settings_databases_combobox(self):
        ''' Обновление содержимого combobox в settings_databases_combobox '''
        db_names = get_all_connections().keys()
        self.settings_databases_combobox.clear()
        self.settings_databases_combobox.addItems(db_names)


    def connect_to_db_button(self):
        db_name = self.settings_databases_combobox.currentText()
        connection = get_connection(db_name)
        if connection is not None:
            connect_to_database(
                connection['username'],
                connection['password'],
                connection['host'],
                connection['port'],
                db_name
            )
        else:
            Logger.log_warning('Database is unselected!')


    def open_dxf_button_click(self):
        """
        Open DXF file and populate tree widget with layers and entities.
        """
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        file_name, _ = QFileDialog.getOpenFileName(self, "Select DXF File", "", "DXF Files (*.dxf);;All Files (*)", options=options)
        if file_name:
            self.dxf_handler.read_dxf_file(file_name, self.refresh_dfx_tree_widget)


    def refresh_dfx_tree_widget(self):
        if self.dxf_handler.file_is_open:
            self.dxf_tree_widget_handler.populate_tree_widget(self.dxf_handler.get_layers())
        else:
            self.dxf_tree_widget_handler.populate_tree_widget({})

        self.select_area_button.setEnabled(self.dxf_handler.file_is_open)
        self.export_to_db_button.setEnabled(self.dxf_handler.file_is_open)

    
    def export_to_db_button_click(self):
        checked_layers = self.dxf_tree_widget_handler.get_all_checked_entities()
        send_layers_to_db('f_' + str(random.randint(0, 10000)), checked_layers)



'''


        self.pushButton.clicked.connect(self.select_dxf_button)
        self.treeWidget.itemChanged.connect(self.handle_item_changed)
        self.importButton.clicked.connect(self.push)
        self.settings_editButton.clicked.connect(self.edit_connections_button)
        self.settings_editButton_2.clicked.connect(self.edit_table_name_button)
        #self.settings_editButton_2.enabled.
        self.settings_connectButton.clicked.connect(self.select_dbcombobox)
        self.settings_dbComboBox.currentIndexChanged.connect(self.select_dbcombobox)
        self.settings_tbComboBox.currentIndexChanged.connect(self.select_tbcombobox)
        event_db_connection_changed.append(self.update_dbcombobox)
        event_db_connection_changed.append(self.update_tbcombobox)
        self.initialize_combobox()
    
        self.truncateCheckBox.stateChanged.connect(self.on_truncate_checked)
        self.onlyMappingCheckBox.stateChanged.connect(self.on_onlyMapping_checked)

        self.dxf_handler = DXFHandler(self.type_shape, self.type_selection)
        Logger.log_message(f'{self.type_shape.currentText()}, {self.type_selection.currentText()}')
        self.tree_widget_handler = TreeWidgetHandler(self.treeWidget)
        self.worker_handler = WorkerHandler()
        self.progress_dialog = None


    def push(self):
        """
        Push selected objects to the database.
        """
        selected_objects = {}
        for layer, data in self.tree_widget_handler.tree_items.items():
            if data['item'].checkState(0) == Qt.Checked:
                for entity_description, entity_item in data['entities'].items():
                    if entity_item.checkState(0) == Qt.Checked:
                        attributes = []
                        geometry = []
                        for i in range(entity_item.childCount()):
                            child = entity_item.child(i)
                            if child.text(0) == 'Атрибуты':
                                attributes = [attr.text(0) for attr in self.tree_widget_handler.get_checked_children(child)]
                            elif child.text(0) == 'Геометрия':
                                geometry = [geom.text(0) for geom in self.tree_widget_handler.get_checked_children(child)]

                        if layer not in selected_objects:
                            selected_objects[layer] = []

                        selected_objects[layer].append({
                            'entity_description': entity_item.text(0),
                            'attributes': attributes,
                            'geometry': geometry
                        })

        if selected_objects:
            layers = []
            for layer_name, entities in selected_objects.items():
                json_data = json.dumps(entities)
                layers.append({
                    'layer_name': layer_name,
                    'json_data': json_data
                })
            self.db_manager.save_layer_set(
                "Example Layer Set", 
                "This is an example layer set.", 
                layers,
                self.table_name, 
                self.truncateCheckBox.isChecked(),
                self.onlyMappingCheckBox.isChecked(),
                self.logCheckBox.isChecked())
            Logger.log_message("Push")
    
    def update_tbcombobox(self):
        db_names = get_all_table_name_in_current_db(self.db_name)
        self.settings_tbComboBox.clear()
        self.settings_tbComboBox.addItems(db_names)

    def select_tbcombobox(self, index):
        if index >= 0:
            db_table_name = self.settings_tbComboBox.itemText(index)
            name = get_table_name_in_current_db(self.db_name, db_table_name)
            self.table_name = name
            # Сохраняем индекс таблицы
            settings = QtCore.QSettings()
            settings.setValue('converter_dialog/tb_index', index)

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.FocusIn and source is self.settings_dbComboBox:
            self.update_dbcombobox()
        return super(ConverterDialog, self).eventFilter(source, event)
    
    def edit_connections_button(self):
        self.edit_dialog = EditConnectionsDialog()
        self.edit_dialog.show()
        result = self.edit_dialog.exec_()
    
    def edit_table_name_button(self):
        self.edit_dialog = EditTableNameDialog(self.db_name)
        self.edit_dialog.show()
        result = self.edit_dialog.exec_()
   
    def initialize_combobox(self):
        # Инициализация сохранённых индексов
        settings = QtCore.QSettings()
        try:
            db_index = int(settings.value('converter_dialog/db_index', 0))
            tb_index = int(settings.value('converter_dialog/tb_index', 0))
        except:
            Logger.log_message(f"Error load data")
            settings.remove('converter_dialog/db_index')
            settings.remove('converter_dialog/tb_index')
            db_index = 0
            tb_index = 0
            
        self.update_dbcombobox()

        # Установка индексов в ComboBox
        self.settings_dbComboBox.setCurrentIndex(db_index)

        # Инициализация db_name и table_name значениями из ComboBox
        if self.settings_dbComboBox.count() > 0:
            self.db_name = self.settings_dbComboBox.itemText(db_index)
        else:
            self.db_name = "None"

        self.update_tbcombobox()  # обновляем таблицы в соответствии с выбранной базой данных
        self.settings_tbComboBox.setCurrentIndex(tb_index)

        if self.settings_tbComboBox.count() > 0:
            self.table_name = self.settings_tbComboBox.itemText(tb_index)
        else:
            self.table_name = "layers"


        Logger.log_message(f"Initialized db_name: {self.db_name}, table_name: {self.table_name}")

    def on_truncate_checked(self, state):
        if state == Qt.Checked:
            self.onlyMappingCheckBox.setChecked(False)

    def on_onlyMapping_checked(self, state):
        if state == Qt.Checked:
            self.truncateCheckBox.setChecked(False)
    
    #TODO: зародыш явного маппирования, но тогда нужно структуру записи в бд менять
    def show_field_mapping_dialog(self, layer_fields, table_columns):
        dialog = FieldMappingDialog(layer_fields, table_columns)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_mapping()
        return None
        
'''

