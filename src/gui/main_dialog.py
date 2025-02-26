import os

from qgis.PyQt import uic, QtWidgets, QtCore
from qgis.PyQt.QtWidgets import QMessageBox, QProgressDialog, QTreeWidgetItem, QPushButton, QWidget, QHBoxLayout, QHeaderView, QFileDialog, QVBoxLayout, QLabel, QLineEdit, QDialog, QDialogButtonBox
from qgis.PyQt.QtCore import Qt
from qgis._core import QgsApplication, QgsAuthMethodConfig

from qgis.core import QgsProviderRegistry, QgsDataSourceUri
from functools import partial

from .preview_components import PreviewDialog, PreviewWidgetFactory
from ..logger.logger import Logger
from ..dxf.dxf_handler import DXFHandler
from ..tree_widget_handler import TreeWidgetHandler
from ..db.database import get_all_files_from_db, import_dxf, delete_dxf
from .info_dialog import InfoDialog
from ..config.help_content import MAIN_DIALOG_HELP
from ..workers.dxf_worker import DXFWorker
from ..workers.long_task_worker import LongTaskWorker
from ..db.connections_manager import ConnectionsManager
from .credentials_dialog import CredentialsDialog

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'main_dialog.ui'))


class ConverterDialog(QtWidgets.QDialog, FORM_CLASS):
    """
    Диалоговое окно для плагина конвертации DXF в БД.
    """

    def __init__(self, iface, parent=None):
        """Конструктор."""
        super(ConverterDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface

        self.dxf_tree_widget_handler = TreeWidgetHandler(self.dxf_tree_widget)
        self.dxf_handler = DXFHandler(self.type_shape, self.type_selection, self.dxf_tree_widget_handler)
        self.db_tree_widget_handler = TreeWidgetHandler(self.db_structure_treewidget)
        self.preview_cache = {}  # Кеш предпросмотров
        self.preview_factory = PreviewWidgetFactory()
        self.plugin_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.worker = None
        self.connections_manager = ConnectionsManager()

        # нажатие по кнопке export_to_db_button
        self.export_to_db_button.clicked.connect(self.export_to_db_button_click)
    
        # нажатие по другой вкладке tabWidget
        self.tabWidget.currentChanged.connect(self.handle_tab_change)

        # Добавление кнопки информации и настройка ее стилей
        self.info_button = QPushButton("?", self)
        self.info_button.setFixedSize(25, 25)
        self.info_button.setStyleSheet("""
            QPushButton {
                border-radius: 12px;
                background-color: #007bff;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        # Перемещаем кнопку в правый верхний угол
        self.info_button.move(self.width() - 35, 10)
        self.info_button.clicked.connect(self.show_help)

    def handle_tab_change(self, index):
        # 0 - dxf-postgis, 1 - postgis - dxf, 2 - setting
        if index == 1:
            self.refresh_db_structure_treewidget()

    def read_multiple_dxf(self, file_names):
        """
        Обработка выбора нескольких DXF файлов и заполнение древовидного виджета слоями и объектами.
        """
        total_files = len(file_names)
        #self.progress_dialog = QProgressDialog("Processing...", "Cancel", 0, total_files, self)
        #self.progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        #self.progress_dialog.canceled.connect(self.cancel_processing)
        #self.progress_dialog.show()

        self.worker = DXFWorker(self.dxf_handler, file_names)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.process_results)
        self.worker.error.connect(self.handle_error)
        
        self.worker.start()

    def update_progress(self, current, total):
        pass
        #if self.progress_dialog:
            #self.progress_dialog.setValue(current)

    def process_results(self, results):
        #self.progress_dialog.close()
        for result in results:
            if result:
                self.dxf_tree_widget_handler.populate_tree_widget(result)
        
        self.export_to_db_button.setEnabled(self.dxf_handler.file_is_open)
        self.select_area_button.setEnabled(self.dxf_handler.file_is_open)

    def handle_error(self, error_message):
        self.progress_dialog.close()
        QMessageBox.critical(self, "Error", f"Error processing DXF files: {error_message}")

    def start_long_task(self, task_id, func, real_func, *args):
        """
        Запускает длительную задачу в отдельном потоке.
        Аргументы:
            task_id (str): Идентификатор задачи.
            func (callable): Функция для выполнения.
            real_func (callable): Функция для выполнения в воркере.
            *args: Список аргументов переменной длины.
        """
        # Create and setup worker
        self.long_task_worker = LongTaskWorker(task_id, func, *args)
        self.long_task_worker.finished.connect(self.on_finished)
        self.long_task_worker.error.connect(self.handle_long_task_error)
        
        # Start the worker thread
        self.long_task_worker.start()

    def handle_long_task_error(self, error_message):
        """Обработчик ошибок длительных задач"""
        QMessageBox.critical(self, "Error", f"Error during task execution: {error_message}")
        #self.progress_dialog.close()

    def on_finished(self, task_id, result):
        """
        Обрабатывает завершение задачи.
        """
        if result is not None:
            if task_id == "read_dxf_file":
                self.dxf_tree_widget_handler.populate_tree_widget(result)
            elif task_id == "select_entities_in_area" and result != []:
                self.dxf_tree_widget_handler.select_area(result)

        self.export_to_db_button.setEnabled(self.dxf_handler.file_is_open)
        self.select_area_button.setEnabled(self.dxf_handler.file_is_open)
        #self.progress_dialog.close()
        
        # Clean up worker
        if hasattr(self, 'long_task_worker'):
            self.long_task_worker.deleteLater()
            self.long_task_worker = None

    def export_to_db_button_click(self):
        from .export_dialog import ExportDialog

        has_selection = any(self.dxf_handler.selected_entities.values())
        
        if has_selection:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setWindowTitle("Export Selection")
            msg_box.setText("Вы хотите экспортировать только выбранные объекты?")
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            
            result = msg_box.exec_()
            
            if result == QMessageBox.Cancel:
                return
            elif result == QMessageBox.No:
                self.dxf_handler.clear_selection()
        
        dlg = ExportDialog(self.dxf_tree_widget_handler, self.dxf_handler)
        dlg.show()
        result = dlg.exec_()         

        # See if OK was pressed
        if result:
            pass
            #TODO: Clear selection after successful export
            #self.dxf_handler.clear_selection()
        
        self.show_window()


    def show_window(self):
        # Показать окно и сделать его активным
        self.raise_()
        self.activateWindow()
        self.show()

    def _get_connection_credentials(self, uri):
        """Gets connection credentials from URI or authentication configuration"""
        username = None
        password = None
        
        # Try all possible ways to get credentials
        methods = [
            lambda: (uri.username(), uri.password()),  # Basic auth
            lambda: self._get_auth_credentials(uri.authConfigId()),  # Auth config
            lambda: self._parse_connection_string(uri.connectionInfo()),  # Connection string
            lambda: self._get_postgres_credentials(uri.service())  # PostgreSQL service file
        ]
        
        for method in methods:
            try:
                u, p = method()
                if u and p:
                    username = u
                    password = p
                    break
            except:
                continue

        return username, password

    def _get_auth_credentials(self, authcfg):
        """Gets credentials from authentication configuration"""
        if authcfg:
            auth_mgr = QgsApplication.authManager()
            auth_cfg = QgsAuthMethodConfig()
            auth_mgr.loadAuthenticationConfig(authcfg, auth_cfg, True)
            return auth_cfg.config('username', ''), auth_cfg.config('password', '')
        return None, None

    def _parse_connection_string(self, conn_info):
        """Parses connection string for credentials"""
        username = None
        password = None
        if conn_info:
            params = conn_info.split(' ')
            for param in params:
                if param.startswith('user='):
                    username = param.split('=')[1].strip("'")
                elif param.startswith('password='):
                    password = param.split('=')[1].strip("'")
        return username, password

    def _get_postgres_credentials(self, service):
        """Gets credentials from PostgreSQL service file"""
        if service:
            # Try to read from PostgreSQL service file
            pgservicefile = os.path.expanduser("~/.pg_service.conf")
            if os.path.exists(pgservicefile):
                with open(pgservicefile, 'r') as f:
                    current_service = None
                    for line in f:
                        line = line.strip()
                        if line.startswith('[') and line.endswith(']'):
                            current_service = line[1:-1]
                        elif current_service == service:
                            if '=' in line:
                                key, value = line.split('=', 1)
                                key = key.strip()
                                value = value.strip()
                                if key == 'user':
                                    username = value
                                elif key == 'password':
                                    password = value
                                    if username:
                                        return username, password
        return None, None

    def refresh_db_structure_treewidget(self):
        """
        Обновление древовидного виджета структуры базы данных
        """
        self.preview_factory.clear_cache()
        self.db_structure_treewidget.clear()
        settings = QgsProviderRegistry.instance().providerMetadata('postgres').connections()

        if not settings:
            no_conn_item = QTreeWidgetItem(["No PostgreSQL connections found"])
            self.db_structure_treewidget.addTopLevelItem(no_conn_item)
            return

        for conn_name, conn_metadata in settings.items():
            Logger.log_message(f"Processing connection {conn_name}")
            try:
                uri = QgsDataSourceUri(conn_metadata.uri())
                
                # Create connection item
                conn_item = QTreeWidgetItem([conn_name])
                self.db_structure_treewidget.addTopLevelItem(conn_item)

                # Create buttons container
                buttons_widget = QWidget()
                buttons_layout = QHBoxLayout(buttons_widget)
                buttons_layout.setContentsMargins(20, 0, 0, 0)

                # Add connect button
                connect_button = QPushButton('Connect')
                connect_button.setFixedSize(80, 20)
                connect_button.clicked.connect(
                    partial(self.connect_to_db, conn_name, conn_item, uri))

                # Add info button
                info_button = QPushButton('info')
                info_button.setFixedSize(80, 20)
                info_button.clicked.connect(
                    partial(self.open_db_info_dialog, conn_name, uri.database(), uri.host(), uri.port()))

                buttons_layout.addWidget(connect_button)
                buttons_layout.addWidget(info_button)
                buttons_layout.setAlignment(Qt.AlignLeft)
                buttons_widget.setLayout(buttons_layout)

                self.db_structure_treewidget.setItemWidget(conn_item, 1, buttons_widget)

            except Exception as e:
                Logger.log_message(f"Error processing connection {conn_name}: {str(e)}")
                error_item = QTreeWidgetItem([f"{conn_name} (Connection error)"])
                self.db_structure_treewidget.addTopLevelItem(error_item)

        # Адаптируем размеры столбцов
        self.db_structure_treewidget.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.db_structure_treewidget.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)

    def connect_to_db(self, conn_name, conn_item, uri):
        """Подключение к базе данных и загрузка файлов"""
        try:
            # Создаем уникальный идентификатор подключения на основе host, port и database
            conn_display_name = f"{uri.host()}:{uri.port()}/{uri.database()}"
            
            # Сначала пробуем найти сохраненные учетные данные по уникальному ключу
            conn = self.connections_manager.get_connection(conn_display_name)
            if conn:
                Logger.log_message(f"Используются сохраненные учетные данные для '{conn_display_name}'")
                username = conn['username']
                password = conn['password']
            else:
                # Пробуем извлечь учетные данные с помощью разных методов
                username, password = None, None
                # Метод 1: Простая авторизация из URI
                if uri.username() and uri.password():
                    username, password = uri.username(), uri.password()
                    Logger.log_message(f"Учетные данные получены из URI для '{conn_name}'")
                
                # Метод 2: AuthConfig
                elif uri.authConfigId():
                    auth_mgr = QgsApplication.authManager()
                    if auth_mgr:
                        auth_cfg = QgsAuthMethodConfig()
                        if auth_mgr.loadAuthenticationConfig(uri.authConfigId(), auth_cfg, True):
                            username = auth_cfg.config('username', '')
                            password = auth_cfg.config('password', '')
                            if username and password:
                                Logger.log_message(f"Учетные данные получены из AuthConfig для '{conn_name}'")
                    
                # Метод 3: Парсинг строки подключения
                elif uri.connectionInfo():
                    conn_info = uri.connectionInfo()
                    params = conn_info.split(' ')
                    for param in params:
                        if param.startswith('user='):
                            username = param.split('=')[1].strip("'")
                        elif param.startswith('password='):
                            password = param.split('=')[1].strip("'")
                    if username and password:
                        Logger.log_message(f"Учетные данные получены из connectionInfo для '{conn_name}'")
                
                # Метод 4: PostgreSQL service file
                elif uri.service():
                    pgservicefile = os.path.expanduser("~/.pg_service.conf")
                    if os.path.exists(pgservicefile):
                        try:
                            with open(pgservicefile, 'r') as f:
                                current_service = None
                                for line in f:
                                    line = line.strip()
                                    if line.startswith('[') and line.endswith(']'):
                                        current_service = line[1:-1]
                                    elif current_service == uri.service() and '=' in line:
                                        key, value = line.split('=', 1)
                                        key, value = key.strip(), value.strip()
                                        if key == 'user':
                                            username = value
                                        elif key == 'password':
                                            password = value
                            if username and password:
                                Logger.log_message(f"Учетные данные получены из pg_service.conf для '{conn_name}'")
                        except Exception as e:
                            Logger.log_error(f"Ошибка при чтении pg_service.conf: {str(e)}")
                    
                # Если не смогли получить учетные данные, запрашиваем у пользователя
                if not (username and password):
                    Logger.log_message(f"Не удалось получить учетные данные автоматически для '{conn_display_name}', запрашиваем ввод")
                    default_username = uri.username() or ''
                    username, password = CredentialsDialog.get_credentials_for_connection(conn_display_name, self, default_username)
                    if username and password:
                        # Сохраняем учетные данные, если пользователь их ввел
                        self.connections_manager.save_connection(conn_display_name, username, password)
                        Logger.log_message(f"Учетные данные для '{conn_display_name}' успешно сохранены")
                    else:
                        Logger.log_message(f"Подключение отменено пользователем для '{conn_display_name}'")
                        return
                else:
                    # Сохраняем автоматически полученные учетные данные для последующего использования
                    self.connections_manager.save_connection(conn_display_name, username, password)
                    Logger.log_message(f"Автоматически полученные учетные данные для '{conn_display_name}' сохранены")

            # Очищаем существующие дочерние элементы
            conn_item.takeChildren()
            
            # Тестируем подключение и получаем файлы
            files = get_all_files_from_db(username, password, uri.host(), 
                                        uri.port(), uri.database())
            
            if files is None or len(files) == 0:
                Logger.log_message(f"База данных '{conn_name}' пуста или не поддерживает структуру хранения")
                conn_item.setText(0, f'{conn_name} (Пусто)')
                # Hide connect button even if DB is empty
                buttons_widget = self.db_structure_treewidget.itemWidget(conn_item, 1)
                if buttons_widget:
                    for child in buttons_widget.children():
                        if isinstance(child, QPushButton) and child.text() == 'Connect':
                            child.hide()
                            break
                return

            # Reset connection name and hide connect button
            conn_item.setText(0, conn_name)
            # Get the buttons widget
            buttons_widget = self.db_structure_treewidget.itemWidget(conn_item, 1)
            if buttons_widget:
                # Find and hide connect button
                for child in buttons_widget.children():
                    if isinstance(child, QPushButton) and child.text() == 'Connect':
                        child.hide()
                        break

            for file in files:
                entity_description = f"{file['filename']}"
                entity_item = QTreeWidgetItem([entity_description])
                conn_item.addChild(entity_item)

                # Создаем контейнер для кнопок
                buttons_widget = QWidget()
                buttons_layout = QHBoxLayout(buttons_widget)
                buttons_layout.setContentsMargins(20, 0, 0, 0)

                # Создаем виджет предпросмотра
                preview_widget = self.preview_factory.create_preview_widget(
                    file['filename'],
                    self.plugin_root_dir,
                    self.show_full_preview
                )
                if preview_widget:
                    buttons_layout.addWidget(preview_widget)

                # Добавляем кнопки
                import_button = QPushButton('import')
                delete_button = QPushButton('delete')
                info_button = QPushButton('info')

                for btn in (import_button, delete_button, info_button):
                    btn.setFixedSize(80, 20)
                    buttons_layout.addWidget(btn)

                # Привязываем обработчики событий
                import_button.clicked.connect(
                    partial(self.import_from_db_button_click, conn_display_name, uri.database(), uri.host(), uri.port(), file['filename'], file['id']))

                delete_button.clicked.connect(
                    partial(self.delete_file_from_db, conn_display_name, uri.database(), uri.host(), uri.port(), file['id'], file['filename']))

                info_button.clicked.connect(
                    partial(self.open_file_info_dialog, file['id'], file['filename'], file['upload_date']))

                buttons_layout.setAlignment(Qt.AlignLeft)
                buttons_widget.setLayout(buttons_layout)

                self.db_structure_treewidget.setItemWidget(entity_item, 1, buttons_widget)

        except Exception as e:
            Logger.log_message(f"Ошибка подключения к базе данных '{conn_name}': {str(e)}")
            conn_item.setText(0, f'{conn_name} (Ошибка подключения: {str(e)})')

    def _prompt_credentials(self, conn_name, default_username=None):
        """Запрашивает у пользователя учетные данные"""
        return CredentialsDialog.get_credentials_for_connection(conn_name, self, default_username)

    def delete_file_from_db(self, conn_display_name, database, host, port, file_id, file_name):
        """
        Удаление файла из базы данных
        """
        # Создаем диалоговое окно
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Удаление файла")
        msg_box.setText(f"Вы действительно хотите удалить файл '{file_name}'?")

        # Добавляем кнопки
        yes_button = msg_box.addButton("Да", QMessageBox.YesRole)
        no_button = msg_box.addButton("Нет", QMessageBox.NoRole)
        cancel_button = msg_box.addButton("Отмена", QMessageBox.RejectRole)

        # Отображаем диалоговое окно
        msg_box.exec_()

        # Проверяем, какую кнопку нажали
        if msg_box.clickedButton() == yes_button:
            saved_conn = self.connections_manager.get_connection(conn_display_name)
            if not saved_conn:
                QMessageBox.warning(None, "Ошибка", "Не найдены сохраненные учетные данные для этого подключения")
                return
                
            # Очищаем кеш перед удалением файла
            preview_path = os.path.join(self.plugin_root_dir, 'previews', f"{os.path.splitext(file_name)[0]}.svg")
            self.preview_factory.remove_from_cache(preview_path)
            
            delete_dxf(saved_conn['username'], saved_conn['password'], host, port, database, file_id)
            self.refresh_db_structure_treewidget()
            

    def open_file_info_dialog(self, file_id, file_name, upload_date):
        """
        Открытие диалога информации о файле
        """
        # Создаем диалоговое окно
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Информация о файле")
        msg_box.setText(f"ID: {file_id}\nИмя файла: {file_name}\nДата загрузки: {upload_date}")

        # Добавляем кнопки
        msg_box.addButton(QMessageBox.Ok)

        # Отображаем диалоговое окно
        msg_box.exec_()


    def open_db_info_dialog(self, conn_name, dbname, host, port):
        """Открытие диалога информации о базе данных"""
        try:
            # Создаем уникальный идентификатор подключения
            conn_display_name = f"{host}:{port}/{dbname}"
            
            # Получаем сохраненные учетные данные из ConnectionsManager
            conn = self.connections_manager.get_connection(conn_display_name)
            if conn:
                username = conn['username']
                password = conn['password']
            else:
                # Если нет сохраненных данных, пробуем получить из URI
                conn_metadata = QgsProviderRegistry.instance().providerMetadata('postgres').connections()[conn_name]
                uri = QgsDataSourceUri(conn_metadata.uri())
                username, password = self._get_connection_credentials(uri)

            info_text = (
                f"Подключение: {conn_name}\n"
                f"База данных: {dbname}\n"
                f"Пользователь: {username or 'Не задано'}\n"
                f"Пароль: {'*' * len(password) if password else 'Не задано'}\n"
                f"Хост: {host}\n"
                f"Порт: {port}"
            )
            
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("Информация о подключении")
            msg_box.setText(info_text)
            msg_box.exec_()
            
        except Exception as e:
            Logger.log_message(f"Ошибка при отображении информации о подключении {conn_name}: {str(e)}")
            QMessageBox.warning(None, "Ошибка", f"Не удалось получить информацию о подключении: {str(e)}")

    def import_from_db_button_click(self, conn_display_name, dbname, host, port, file_name, file_id):
        """
        Обработка нажатия кнопки импорта из базы данных
        """
        # Открываем диалоговое окно для выбора пути сохранения файла
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(None, "Save file as", "", "Все файлы (*)", options=options)
        
        if file_path:
            conn = self.connections_manager.get_connection(conn_display_name)
            if not conn:
                QMessageBox.warning(None, "Ошибка", "Не найдены сохраненные учетные данные для этого подключения")
                return
                
            import_dxf(conn['username'], conn['password'], host, port, dbname, file_id, file_path)
        else:
            QMessageBox.warning(None, "Ошибка", "Пожалуйста, выберите путь для сохранения файла.")

    def show_full_preview(self, svg_path):
        """Показывает диалог предпросмотра в полном размере"""
        dialog = PreviewDialog(svg_path, self)
        dialog.exec_()

    def show_help(self):
        """Показать диалог помощи с информацией об интерфейсе"""
        help_dialog = InfoDialog("Help - DXF-PostGIS Converter", MAIN_DIALOG_HELP, self)
        help_dialog.exec_()

    def resizeEvent(self, event):
        """Обработка изменения размера окна для сохранения кнопки информации в правильной позиции"""
        super().resizeEvent(event)
        if hasattr(self, 'info_button'):
            self.info_button.move(self.width() - 35, 10)
