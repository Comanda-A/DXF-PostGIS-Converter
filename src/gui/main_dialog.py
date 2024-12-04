import os
import asyncio

from qgis.PyQt import uic, QtWidgets, QtCore
from qgis.PyQt.QtWidgets import QMessageBox, QProgressDialog, QTreeWidgetItem, QPushButton, QWidget, QHBoxLayout, QHeaderView, QFileDialog
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProviderRegistry, QgsDataSourceUri
from functools import partial


from ..logger.logger import Logger
from ..db.saved_connections_manager import get_all_connections, get_connection, edit_connection_via_dialog
from ..dxf.dxf_handler import DXFHandler
from ..tree_widget_handler import TreeWidgetHandler
from ..db.database import get_all_files_from_db, import_dxf, delete_dxf


# Load UI file for PyQt
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'main_dialog.ui'))


class ConverterDialog(QtWidgets.QDialog, FORM_CLASS):
    """
    Dialog class for the DXF to DB converter plugin.
    """

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(ConverterDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface

        self.dxf_handler = DXFHandler(self.type_shape, self.type_selection)
        self.dxf_tree_widget_handler = TreeWidgetHandler(self.dxf_tree_widget)
        self.db_tree_widget_handler = TreeWidgetHandler(self.db_structure_treewidget)

        # нажатие по кнопке export_to_db_button
        self.export_to_db_button.clicked.connect(self.export_to_db_button_click)

        # нажатие по другой вкладке tabWidget
        self.tabWidget.currentChanged.connect(self.handle_tab_change)

    def handle_tab_change(self, index):
        # 0 - dxf-postgis, 1 - postgis - dxf, 2 - setting
        if index == 1:
            self.refresh_db_structure_treewidget()

    def refresh_settings_databases_combobox(self):
        ''' Обновление содержимого combobox в settings_databases_combobox '''
        db_names = get_all_connections().keys()
        self.settings_databases_combobox.clear()
        self.settings_databases_combobox.addItems(db_names)

    def connect_to_db_button(self):
        db_name = self.settings_databases_combobox.currentText()
        connection = get_connection(db_name)
        if connection is not None:
            Logger.log_warning('пока что не работает')
        else:
            Logger.log_warning('Database is unselected!')

    async def read_dxf(self, file_name):
        """
        Handle DXF file selection and populate tree widget with layers and entities.
        """
        self.label.setText(os.path.basename(file_name))
        await self.start_long_task("read_dxf_file", self.dxf_handler.read_dxf_file, self.dxf_handler, file_name)

    async def read_multiple_dxf(self, file_names):
        """
        Handle multiple DXF file selections and populate tree widget with layers and entities.
        """
        total_files = len(file_names)
        self.progress_dialog = QProgressDialog("Processing...", "Cancel", 0, total_files, self)
        self.progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        self.progress_dialog.show()

        tasks = [self.read_dxf(file_name) for file_name in file_names]
        await asyncio.gather(*tasks)

    async def start_long_task(self, task_id, func, real_func, *args):
        """
        Starts a long task by creating a progress dialog and connecting it to a worker handler.
        Args:
            task_id (str): The identifier of the task.
            func (callable): The function to be executed.
            real_func (callable): The function to be executed in the worker.
            *args: Variable length argument list.
        """

        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, func, *args)
        result = await future

        self.on_finished(task_id, result)

    def on_finished(self, task_id, result):
        """
        Handles the completion of a task by stopping the worker.
        """
        if result is not None:
            if task_id == "read_dxf_file":
                self.dxf_tree_widget_handler.populate_tree_widget(result)
            elif task_id == "select_entities_in_area":
                self.dxf_tree_widget_handler.select_area(result)

        self.export_to_db_button.setEnabled(self.dxf_handler.file_is_open)
        self.select_area_button.setEnabled(self.dxf_handler.file_is_open)
        self.progress_dialog.close()

    def refresh_dfx_tree_widget(self):
        if self.dxf_handler.file_is_open:
            self.dxf_tree_widget_handler.populate_tree_widget(self.dxf_handler.get_layers())
        else:
            self.dxf_tree_widget_handler.populate_tree_widget({})

        self.select_area_button.setEnabled(self.dxf_handler.file_is_open)
        self.export_to_db_button.setEnabled(self.dxf_handler.file_is_open)


    def export_to_db_button_click(self):
        from .export_dialog import ExportDialog

        dlg = ExportDialog(self.dxf_tree_widget_handler, self.dxf_handler)
        dlg.show()
        result = dlg.exec_()         

        # See if OK was pressed
        if result:
            pass
        
        self.show_window()


    def show_window(self):
        # Показать окно и сделать его активным
        self.raise_()
        self.activateWindow()
        self.show()


    def refresh_db_structure_treewidget(self):
        self.db_structure_treewidget.clear()
        # Получаем список всех зарегистрированных подключений PostGIS
        settings = QgsProviderRegistry.instance().providerMetadata('postgres').connections()

        for conn_name, conn_metadata in settings.items():
            uri = QgsDataSourceUri(conn_metadata.uri())
            conn_item = QTreeWidgetItem([conn_name])
            self.db_structure_treewidget.addTopLevelItem(conn_item)

            info_button = QPushButton('info')  # Создаем кнопку
            info_button.setFixedSize(80, 20)
            info_button.clicked.connect(
                partial(self.open_db_info_dialog, conn_name, uri.database(), uri.host(), uri.port()))
            widget = QWidget()  # Создаем контейнер для кнопки
            layout = QHBoxLayout(widget)
            layout.addWidget(info_button)
            layout.setAlignment(Qt.AlignLeft)
            layout.setContentsMargins(0, 0, 0, 0)
            widget.setLayout(layout)
            self.db_structure_treewidget.setItemWidget(conn_item, 1, widget)

            self.db_structure_treewidget.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            self.db_structure_treewidget.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)

            conn = get_connection(conn_name) or {}
            username = conn.get('username', 'N/A')
            password = conn.get('password', 'N/A')
            files = get_all_files_from_db(username, password, uri.host(), uri.port(), uri.database())

            if files is None:
                conn_item.setText(0, f'{conn_name} (Error when receiving data)')
            else:
                for file in files:
                    entity_description = f"{file['filename']}"
                    entity_item = QTreeWidgetItem([entity_description])
                    conn_item.addChild(entity_item)

                    # Создаем кнопки "Импорт", "Удалить", "Информация"
                    import_button = QPushButton('import')
                    delete_button = QPushButton('delete')
                    info_button = QPushButton('info')

                    # Задаем размер кнопок
                    import_button.setFixedSize(80, 20)
                    delete_button.setFixedSize(80, 20)
                    info_button.setFixedSize(80, 20)

                    # Привязываем обработчики событий
                    import_button.clicked.connect(
                        partial(self.import_from_db_button_click, conn_name, uri.database(), uri.host(), uri.port(), file['filename'], file['id']))

                    delete_button.clicked.connect(
                        partial(self.delete_file_from_db, conn_name, uri.database(), uri.host(), uri.port(), file['id'], file['filename']))

                    info_button.clicked.connect(
                        partial(self.open_file_info_dialog, file['id'], file['filename'], file['upload_date']))

                    # Создаем контейнер для кнопок
                    widget = QWidget()
                    layout = QHBoxLayout(widget)
                    layout.addWidget(import_button)
                    layout.addWidget(delete_button)
                    layout.addWidget(info_button)
                    layout.setAlignment(Qt.AlignLeft)
                    layout.setContentsMargins(20, 0, 0, 0)
                    widget.setLayout(layout)

                    # Добавляем контейнер в соответствующую колонку узла дерева
                    self.db_structure_treewidget.setItemWidget(entity_item, 1, widget)

    def delete_file_from_db(self, conn_name, database, host, port, file_id, file_name):
        # Создаем диалоговое окно
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("File deletion")
        msg_box.setText(f"Do you really want to delete the file '{file_name}'?")

        # Добавляем кнопки
        yes_button = msg_box.addButton("Yes", QMessageBox.YesRole)
        no_button = msg_box.addButton("No", QMessageBox.NoRole)
        cancel_button = msg_box.addButton("Cancel", QMessageBox.RejectRole)

        # Отображаем диалоговое окно
        msg_box.exec_()

        # Проверяем, какую кнопку нажали
        if msg_box.clickedButton() == yes_button:
            conn = get_connection(conn_name) or {}
            username = conn.get('username', 'N/A')
            password = conn.get('password', 'N/A')
            delete_dxf(username, password, host, port, database, file_id)
            self.refresh_db_structure_treewidget()
            

    def open_file_info_dialog(self, file_id, file_name, upload_date):
        # Создаем диалоговое окно
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("File Info")
        msg_box.setText(f"ID: {file_id}\nFile name: {file_name}\nUpload date: {upload_date}")

        # Добавляем кнопки
        msg_box.addButton(QMessageBox.Ok)

        # Отображаем диалоговое окно
        msg_box.exec_()


    def open_db_info_dialog(self, conn_name, dbname, host, port):
        # Получаем данные о подключении
        conn = get_connection(conn_name) or {}
        username = conn.get('username', 'N/A')
        password = conn.get('password', 'N/A')

        # Формируем текст для отображения
        info_text = (
            f"Connection: {conn_name}\n"
            f"Database: {dbname}\n"
            f"Username: {username}\n"
            f"Password: {password}\n"
            f"Host: {host}\n"
            f"Port: {port}"
        )

        # Создаем диалоговое окно
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Database Connection Info")
        msg_box.setText(info_text)

        # Добавляем кнопки
        edit_button = msg_box.addButton("Edit", QMessageBox.ActionRole)
        ok_button = msg_box.addButton(QMessageBox.Ok)

        # Отображаем диалоговое окно
        msg_box.exec_()

        # Проверяем, какую кнопку нажали
        if msg_box.clickedButton() == edit_button:
            edit_connection_via_dialog(conn_name)
            self.refresh_db_structure_treewidget()
            self.open_db_info_dialog(conn_name, dbname, host, port)


    def import_from_db_button_click(self, conn_name, dbname, host, port, file_name, file_id):
        # Открываем диалоговое окно для выбора пути сохранения файла
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(None, "Save file as", "", "Все файлы (*)", options=options)
        
        conn = get_connection(conn_name) or {}
        username = conn.get('username', 'N/A')
        password = conn.get('password', 'N/A')

        if file_path:
            import_dxf(username, password, host, port, dbname, file_id, file_path)
        else:
            QMessageBox.warning(None, "Error", "Please select the path to save the file.")
