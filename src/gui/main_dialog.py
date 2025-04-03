import os

from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import QMessageBox, QTreeWidgetItem, QPushButton, QWidget, QHBoxLayout, QHeaderView, QFileDialog
from qgis.PyQt.QtCore import Qt

from qgis.core import QgsProviderRegistry, QgsDataSourceUri, QgsSettings
from functools import partial

from .preview_components import PreviewDialog, PreviewWidgetFactory
from ..logger.logger import Logger
from ..dxf.dxf_handler import DXFHandler, get_selected_file
from ..tree_widget_handler import TreeWidgetHandler
from ..db.database import get_all_files_from_db, import_dxf, delete_dxf
from .info_dialog import InfoDialog
from ..workers.dxf_worker import DXFWorker
from ..workers.long_task_worker import LongTaskWorker
from ..db.connections_manager import ConnectionsManager
from ..localization.localization_manager import LocalizationManager

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
        self.lm = LocalizationManager.instance()  # Инициализация менеджера локализации
        self.setupUiText()

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
        
        # нажатие по кнопке export_to_file_button
        self.export_to_file_button.clicked.connect(self.export_to_file_button_click)
    
        # нажатие по другой вкладке tabWidget
        self.tabWidget.currentChanged.connect(self.handle_tab_change)

        # Инициализация состояния чекбокса логирования
        self.settings = QgsSettings()
        enable_logging = self.settings.value("DXFPostGISConverter/EnableLogging", False, type=bool)
        self.enable_logging_checkbox.setChecked(enable_logging)
        self.enable_logging_checkbox.stateChanged.connect(self.toggle_logging)
        
        # Обновляем логгер с текущей настройкой
        Logger.set_logging_enabled(enable_logging)

        # --- New: Инициализация переключателя языка ---
        self.language_combo.setCurrentText(self.lm.current_language)
        self.language_combo.currentTextChanged.connect(self.change_language)

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

    def setupUiText(self):
        """Обновляет текст элементов пользовательского интерфейса согласно выбранному языку"""
        # Заголовок окна
        self.setWindowTitle(self.lm.get_string("UI", "main_dialog_title"))
        
        # Заголовки вкладок
        self.tabWidget.setTabText(0, self.lm.get_string("UI", "tab_dxf_to_sql"))
        self.tabWidget.setTabText(1, self.lm.get_string("UI", "tab_sql_to_dxf"))
        self.tabWidget.setTabText(2, self.lm.get_string("UI", "tab_settings"))
        
        self.open_dxf_button.setText(self.lm.get_string("UI", "open_dxf_button"))
        self.language_label.setText(self.lm.get_string("UI", "interface_language"))        
        self.enable_logging_checkbox.setText(self.lm.get_string("UI", "enable_logs"))                     
        self.settings_structureLabel_2.setText(self.lm.get_string("UI", "databases_label")) 
        self.type_selection.clear()
        self.type_selection.addItem(self.lm.get_string("UI", "selection_intersect"))        
        self.type_selection.addItem(self.lm.get_string("UI", "selection_outside"))        
        self.type_selection.addItem(self.lm.get_string("UI", "selection_inside"))
        self.type_shape.clear()                 
        self.type_shape.addItem(self.lm.get_string("UI", "shape_polygon"))        
        self.type_shape.addItem(self.lm.get_string("UI", "shape_circle"))        
        self.type_shape.addItem(self.lm.get_string("UI", "shape_rectangle"))        
        self.label_3.setText(self.lm.get_string("UI", "type_selection"))        
        self.label_2.setText(self.lm.get_string("UI", "type_shape"))        
        self.label.setText(self.lm.get_string("UI", "file_not_selected"))        
        self.select_area_button.setText(self.lm.get_string("UI", "select_area_button"))
        self.export_to_db_button.setText(self.lm.get_string("UI", "export_to_db_button"))
        

    def check_selected_file(self):
        active_layer = get_selected_file(self.dxf_tree_widget_handler)
        if active_layer:
            Logger.log_message(f"Активный файл: {active_layer}")
            return True
        else:
            Logger.log_warning("Файл не выбран. Пожалуйста, выберите файл в дереве.")
            return False

    def toggle_logging(self, state):
        """
        Включение или отключение логирования при изменении состояния чекбокса.
        """
        is_enabled = state == Qt.Checked
        self.settings.setValue("DXFPostGISConverter/EnableLogging", is_enabled)
        Logger.set_logging_enabled(is_enabled)
        status_text = self.lm.get_string("LOGGING", "logging_enabled" if is_enabled else "logging_disabled")
        Logger.log_message(status_text)

    def handle_tab_change(self, index):
        # 0 - dxf-postgis, 1 - postgis - dxf, 2 - setting
        if index == 1:
            self.refresh_db_structure_treewidget()

    def read_multiple_dxf(self, file_names):
        """
        Обработка выбора нескольких DXF файлов и заполнение древовидного виджета слоями и объектами.
        """
        self.worker = DXFWorker(self.dxf_handler, file_names)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.process_results)
        self.worker.error.connect(self.handle_error)
        
        self.worker.start()

    def update_progress(self, current, total):
        pass

    def process_results(self, results):
        for result in results:
            if result:
                self.dxf_tree_widget_handler.populate_tree_widget(result)
        
        self.export_to_db_button.setEnabled(self.dxf_handler.file_is_open)
        self.select_area_button.setEnabled(self.dxf_handler.file_is_open)

    def handle_error(self, error_message):
        self.progress_dialog.close()
        QMessageBox.critical(self, self.lm.get_string("COMMON", "error"), 
                            self.lm.get_string("MAIN_DIALOG", "error_processing_dxf", error_message))

    def start_long_task(self, task_id, func, *args):
        """
        Запускает длительную задачу в отдельном потоке.
        Аргументы:
            task_id (str): Идентификатор задачи.
            func (callable): Функция для выполнения.
            real_func (callable): Функция для выполнения в воркере.
            *args: Список аргументов переменной длины.
        """
        self.long_task_worker = LongTaskWorker(task_id, func, *args)
        self.long_task_worker.finished.connect(self.on_finished)
        self.long_task_worker.error.connect(self.handle_long_task_error)
        
        self.long_task_worker.start()

    def handle_long_task_error(self, error_message):
        """Обработчик ошибок длительных задач"""
        QMessageBox.critical(self, self.lm.get_string("COMMON", "error"), 
                            self.lm.get_string("MAIN_DIALOG", "error_executing_task", error_message))

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

        if hasattr(self, 'long_task_worker'):
            self.long_task_worker.deleteLater()
            self.long_task_worker = None

    def export_to_db_button_click(self):
        from .export_dialog import ExportDialog

        has_selection = any(self.dxf_handler.selected_entities.values())
        
        if has_selection:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setWindowTitle(self.lm.get_string("MAIN_DIALOG", "export_to_db"))
            msg_box.setText(self.lm.get_string("MAIN_DIALOG", "export_selected_question"))
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            
            result = msg_box.exec_()
            
            if result == QMessageBox.Cancel:
                return
            elif result == QMessageBox.No:
                self.dxf_handler.clear_selection()
        
        dlg = ExportDialog(self.dxf_tree_widget_handler, self.dxf_handler)
        dlg.show()
        result = dlg.exec_()
        if result:
            pass

        self.show_window()

    def show_window(self):
        # Показать окно и сделать его активным
        self.raise_()
        self.activateWindow()
        self.show()

    def refresh_db_structure_treewidget(self):
        """
        Обновление древовидного виджета структуры базы данных
        """
        self.preview_factory.clear_cache()
        self.db_structure_treewidget.clear()
        settings = QgsProviderRegistry.instance().providerMetadata('postgres').connections()

        if not settings:
            no_conn_item = QTreeWidgetItem([self.lm.get_string("MAIN_DIALOG", "no_connections")])
            self.db_structure_treewidget.addTopLevelItem(no_conn_item)
            return

        for conn_name, conn_metadata in settings.items():
            Logger.log_message(self.lm.get_string("LOGGING", "processing_connection", conn_name))
            try:
                uri = QgsDataSourceUri(conn_metadata.uri())
                
                # Создаем элемент подключения
                conn_item = QTreeWidgetItem([conn_name])
                self.db_structure_treewidget.addTopLevelItem(conn_item)

                # Создаем контейнер для кнопок
                buttons_widget = QWidget()
                buttons_layout = QHBoxLayout(buttons_widget)
                buttons_layout.setContentsMargins(20, 0, 0, 0)

                # Добавляем кнопку подключения
                connect_button = QPushButton(self.lm.get_string("MAIN_DIALOG", "connect_button"))
                connect_button.setFixedSize(80, 20)
                connect_button.clicked.connect(
                    partial(self.connect_to_db, conn_name, conn_item, uri))

                # Добавляем кнопку информации
                info_button = QPushButton(self.lm.get_string("MAIN_DIALOG", "info_button"))
                info_button.setFixedSize(80, 20)
                info_button.clicked.connect(
                    partial(self.open_db_info_dialog, conn_name, uri.database(), uri.host(), uri.port()))

                buttons_layout.addWidget(connect_button)
                buttons_layout.addWidget(info_button)
                buttons_layout.setAlignment(Qt.AlignLeft)
                buttons_widget.setLayout(buttons_layout)

                self.db_structure_treewidget.setItemWidget(conn_item, 1, buttons_widget)

            except Exception as e:
                Logger.log_message(f"Ошибка обработки подключения {conn_name}: {str(e)}")
                error_item = QTreeWidgetItem([f"{conn_name} ({self.lm.get_string('MAIN_DIALOG', 'connection_error', '')}"])
                self.db_structure_treewidget.addTopLevelItem(error_item)

        # Адаптируем размеры столбцов
        self.db_structure_treewidget.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.db_structure_treewidget.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)

    def connect_to_db(self, conn_name, conn_item, uri):
        """Подключение к базе данных и загрузка файлов"""
        try:
            # Получаем учетные данные через универсальный метод ConnectionsManager
            username, password = self.connections_manager.get_credentials(
                uri.host(), 
                uri.port(), 
                uri.database(),
                default_username=uri.username(),
                parent=self
            )
            
            if not username or not password:
                Logger.log_message(f"Не удалось получить учетные данные для подключения '{conn_name}'")
                return
                
            # Очищаем существующие дочерние элементы
            conn_item.takeChildren()
            
            # Тестируем подключение и получаем файлы
            files = get_all_files_from_db(username, password, uri.host(), 
                                        uri.port(), uri.database())
            
            if files is None or len(files) == 0:
                Logger.log_message(self.lm.get_string("MAIN_DIALOG", "db_empty_message", conn_name))
                conn_item.setText(0, f'{conn_name} ({self.lm.get_string("MAIN_DIALOG", "db_empty")})')
                # Скрываем кнопку подключения, даже если БД пуста
                buttons_widget = self.db_structure_treewidget.itemWidget(conn_item, 1)
                if buttons_widget:
                    for child in buttons_widget.children():
                        if isinstance(child, QPushButton) and child.text() == self.lm.get_string("MAIN_DIALOG", "connect_button"):
                            child.hide()
                            break
                return

            # Создаем уникальный идентификатор подключения для использования в других методах
            conn_display_name = f"{uri.host()}:{uri.port()}/{uri.database()}"

            # Сбрасываем имя подключения и скрываем кнопку подключения
            conn_item.setText(0, conn_name)
            # Получаем виджет с кнопками
            buttons_widget = self.db_structure_treewidget.itemWidget(conn_item, 1)
            if buttons_widget:
                # Находим и скрываем кнопку подключения
                for child in buttons_widget.children():
                    if isinstance(child, QPushButton) and child.text() == self.lm.get_string("MAIN_DIALOG", "connect_button"):
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
                import_button = QPushButton(self.lm.get_string("MAIN_DIALOG", "import_button"))
                delete_button = QPushButton(self.lm.get_string("MAIN_DIALOG", "delete_button"))
                info_button = QPushButton(self.lm.get_string("MAIN_DIALOG", "info_button"))

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
            conn_item.setText(0, f'{conn_name} ({self.lm.get_string("MAIN_DIALOG", "connection_error", str(e))})')

    def delete_file_from_db(self, conn_display_name, database, host, port, file_id, file_name):
        """
        Удаление файла из базы данных
        """
        # Создаем диалоговое окно
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle(self.lm.get_string("MAIN_DIALOG", "delete_file_title"))
        msg_box.setText(self.lm.get_string("MAIN_DIALOG", "delete_file_question", file_name))

        # Добавляем кнопки
        yes_button = msg_box.addButton(self.lm.get_string("COMMON", "yes"), QMessageBox.YesRole)
        no_button = msg_box.addButton(self.lm.get_string("COMMON", "no"), QMessageBox.NoRole)
        cancel_button = msg_box.addButton(self.lm.get_string("COMMON", "cancel"), QMessageBox.RejectRole)

        # Отображаем диалоговое окно
        msg_box.exec_()

        # Проверяем, какую кнопку нажали
        if msg_box.clickedButton() == yes_button:
            saved_conn = self.connections_manager.get_connection(conn_display_name)
            if not saved_conn:
                QMessageBox.warning(None, self.lm.get_string("COMMON", "error"), 
                                   self.lm.get_string("MAIN_DIALOG", "saved_credentials_error"))
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
        msg_box.setWindowTitle(self.lm.get_string("MAIN_DIALOG", "file_info_title"))
        msg_box.setText(self.lm.get_string("MAIN_DIALOG", "file_info_text", file_id, file_name, upload_date))

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
                # Если нет сохраненных данных, выводим сообщение
                username = self.lm.get_string("MAIN_DIALOG", "not_saved")
                password = self.lm.get_string("MAIN_DIALOG", "not_saved")

            password_display = '*' * len(password) if password and password != self.lm.get_string("MAIN_DIALOG", "not_saved") else self.lm.get_string("MAIN_DIALOG", "not_saved")
            
            info_text = self.lm.get_string("MAIN_DIALOG", "db_info_text", 
                                          conn_name, dbname, username, password_display, host, port)
            
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle(self.lm.get_string("MAIN_DIALOG", "db_info_title"))
            msg_box.setText(info_text)
            msg_box.exec_()
            
        except Exception as e:
            Logger.log_message(self.lm.get_string("MAIN_DIALOG", "error_displaying_connection", conn_name, str(e)))
            QMessageBox.warning(None, self.lm.get_string("COMMON", "error"), 
                               self.lm.get_string("MAIN_DIALOG", "error_displaying_connection", conn_name, str(e)))

    def import_from_db_button_click(self, conn_display_name, dbname, host, port, file_name, file_id):
        """
        Обработка нажатия кнопки импорта из базы данных
        """
        # Открываем диалоговое окно для выбора пути сохранения файла
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(None, self.lm.get_string("MAIN_DIALOG", "save_file_as"), 
                                                 f"{file_name}", "DXF файлы (*.dxf);;Все файлы (*)", options=options)
        
        if file_path:
            conn = self.connections_manager.get_connection(conn_display_name)
            if not conn:
                QMessageBox.warning(None, self.lm.get_string("COMMON", "error"), 
                                   self.lm.get_string("MAIN_DIALOG", "saved_credentials_error"))
                return
                
            import_dxf(conn['username'], conn['password'], host, port, dbname, file_id, file_path)
        else:
            QMessageBox.warning(None, self.lm.get_string("COMMON", "warning"), 
                               self.lm.get_string("MAIN_DIALOG", "file_path_error"))

    def show_full_preview(self, svg_path):
        """Показывает диалог предпросмотра в полном размере"""
        dialog = PreviewDialog(svg_path, self)
        dialog.exec_()

    def show_help(self):
        """Показать диалог помощи с информацией об интерфейсе"""
        help_dialog = InfoDialog(self.lm.get_string("MAIN_DIALOG", "help_dialog_title"),
                                 self.lm.get_string("HELP_CONTENT", "MAIN_DIALOG"), self)
        help_dialog.exec_()

    def resizeEvent(self, event):
        """Обработка изменения размера окна для сохранения кнопки информации в правильной позиции"""
        super().resizeEvent(event)
        if hasattr(self, 'info_button'):
            self.info_button.move(self.width() - 35, 10)

    def change_language(self, new_lang):
        """Обработка смены языка через переключатель"""
        self.lm.set_language(new_lang)
        Logger.log_message(f"Язык изменен на {new_lang}")
        # Optionally, trigger UI re-translation if needed
        # For example: self.retranslateUi(self)
        self.setupUiText()

    def export_to_file_button_click(self):
        """
        Обработка нажатия кнопки экспорта выбранных объектов в файл.
        Использует DXFExporter для экспорта выбранных сущностей в новый DXF-файл.
        """
        from ..dxf.dxf_handler import DXFExporter
        
        # Проверяем, выбран ли файл
        active_file = get_selected_file(self.dxf_tree_widget_handler)
        if not active_file:
            QMessageBox.warning(self, self.lm.get_string("COMMON", "warning"), 
                               self.lm.get_string("MAIN_DIALOG", "no_file_selected"))
            return
        
        # Проверяем, выбраны ли объекты
        if active_file not in self.dxf_handler.selected_entities or not self.dxf_handler.selected_entities[active_file]:
            QMessageBox.warning(self, self.lm.get_string("COMMON", "warning"), 
                               self.lm.get_string("MAIN_DIALOG", "no_entities_selected"))
            return
            
        # Открываем диалог для выбора пути сохранения файла
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            self.lm.get_string("MAIN_DIALOG", "export_file_as"), 
            f"{os.path.splitext(active_file)[0]}_export.dxf",
            "DXF файлы (*.dxf);;Все файлы (*)", 
            options=options
        )
        
        if not file_path:
            return
            
        # Создаем экспортер и выполняем два метода экспорта
        exporter = DXFExporter(self.dxf_handler)
        
        # Показываем диалог с выбором метода экспорта
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle(self.lm.get_string("MAIN_DIALOG", "export_method_title"))
        msg_box.setText(self.lm.get_string("MAIN_DIALOG", "export_method_question"))
        
        simple_button = msg_box.addButton(self.lm.get_string("MAIN_DIALOG", "export_simple"), QMessageBox.YesRole)
        #resources_button = msg_box.addButton(self.lm.get_string("MAIN_DIALOG", "export_with_resources"), QMessageBox.NoRole)
        cancel_button = msg_box.addButton(self.lm.get_string("COMMON", "cancel"), QMessageBox.RejectRole)
        
        msg_box.exec_()
        
        try:
            result = False
            if msg_box.clickedButton() == simple_button:
                # Простой экспорт с использованием write_block
                Logger.log_message(f"Выполняется простой экспорт в файл: {file_path}")
                result = exporter.export_selected_entities(active_file, file_path)
            elif msg_box.clickedButton() == resources_button:
                # Экспорт с дополнительными ресурсами
                Logger.log_message(f"Выполняется экспорт с ресурсами в файл: {file_path}")
                result = exporter.export_with_resources(active_file, file_path)
            else:
                # Отмена операции
                return
                
            # Проверяем результат экспорта
            if result:
                QMessageBox.information(
                    self, 
                    self.lm.get_string("COMMON", "success"),
                    self.lm.get_string("MAIN_DIALOG", "export_successful", file_path)
                )
            else:
                QMessageBox.warning(
                    self, 
                    self.lm.get_string("COMMON", "error"),
                    self.lm.get_string("MAIN_DIALOG", "export_error")
                )
        except Exception as e:
            Logger.log_error(f"Ошибка при экспорте в файл: {str(e)}")
            QMessageBox.critical(
                self, 
                self.lm.get_string("COMMON", "error"),
                self.lm.get_string("MAIN_DIALOG", "export_exception", str(e))
            )
