import os
import tempfile

from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import QMessageBox, QTreeWidgetItem, QPushButton, QWidget, QHBoxLayout, QHeaderView, QFileDialog, QProgressDialog
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QTimer

from qgis.core import QgsProviderRegistry, QgsDataSourceUri, QgsSettings
from functools import partial

from .preview_components import PreviewDialog, PreviewWidgetFactory
from .qgis_layer_sync_manager import QGISLayerSyncManager
from ..db.database import get_all_dxf_files, delete_dxf_file, get_dxf_file_by_id
from ..logger.logger import Logger
from ..dxf.dxf_handler import DXFHandler, get_selected_file
from ..tree_widget_handler import TreeWidgetHandler
from .info_dialog import InfoDialog
from .import_destination_dialog import ImportDestinationDialog
from ..workers.dxf_worker import DXFWorker
from ..workers.long_task_worker import LongTaskWorker
from ..db.connections_manager import ConnectionsManager
from ..localization.localization_manager import LocalizationManager

class PreviewGeneratorThread(QThread):
    """
    Поток для генерации превью DXF файла.
    Работает отдельно от основного потока интерфейса, чтобы не блокировать UI.
    """
    finished = pyqtSignal(bool, str, str)  # Сигнал: успех/неуспех, сообщение, путь к превью
    progress_update = pyqtSignal(int, str)  # Сигнал обновления прогресса: процент, сообщение
    
    def __init__(self, dxf_handler, file_content, filename, plugin_root_dir):
        """
        Инициализация потока генерации превью.
        
        :param dxf_handler: Обработчик DXF-файлов
        :param file_content: Содержимое DXF-файла в бинарном формате
        :param filename: Имя DXF-файла
        :param plugin_root_dir: Корневая директория плагина
        """
        super().__init__()
        self.dxf_handler = dxf_handler
        self.file_content = file_content
        self.filename = filename
        self.plugin_root_dir = plugin_root_dir
        self.lm = LocalizationManager.instance()
        self.temp_file_path = None

    def run(self):
        """
        Основной метод потока. Выполняет генерацию превью и отправляет сигнал о результате.
        """
        try:
            Logger.log_message(self.lm.get_string("MAIN_DIALOG", "preview_generation_started", self.filename))
            
            self.progress_update.emit(0, self.lm.get_string("MAIN_DIALOG", "creating_temp_file"))
            
            # Создаем временный файл
            temp_dir = tempfile.gettempdir()
            self.temp_file_path = os.path.join(temp_dir, self.filename)
            
            # Записываем содержимое файла во временный файл
            with open(self.temp_file_path, 'wb') as f:
                f.write(self.file_content)
            
            self.progress_update.emit(30, self.lm.get_string("MAIN_DIALOG", "reading_dxf_file"))
            
            # Создаем SVG превью
            doc = self.dxf_handler.simle_read_dxf_file(self.temp_file_path)
            
            self.progress_update.emit(60, self.lm.get_string("MAIN_DIALOG", "generating_svg"))
            
            preview_path = self.dxf_handler.save_svg_preview(doc, doc.modelspace(), self.filename)
            
            self.progress_update.emit(90, self.lm.get_string("MAIN_DIALOG", "cleaning_temp_files"))
            
            # Удаляем временный файл
            try:
                os.remove(self.temp_file_path)
                self.temp_file_path = None
            except Exception as e:
                Logger.log_warning(f"Не удалось удалить временный файл {self.temp_file_path}: {str(e)}")
            
            if preview_path:
                Logger.log_message(self.lm.get_string("MAIN_DIALOG", "preview_generation_success", preview_path))
                self.finished.emit(True, self.lm.get_string("MAIN_DIALOG", "preview_generation_complete"), preview_path)
            else:
                Logger.log_error("Генерация превью не удалась")
                self.finished.emit(False, self.lm.get_string("MAIN_DIALOG", "preview_generation_error"), "")
                
        except Exception as e:
            Logger.log_error(f"Ошибка при генерации превью: {str(e)}")
            self.finished.emit(False, str(e), "")
            
    def cleanup(self):
        """Очистка временных файлов при прерывании работы потока"""
        if self.temp_file_path and os.path.exists(self.temp_file_path):
            try:
                os.remove(self.temp_file_path)
                Logger.log_message(f"Временный файл удален при очистке: {self.temp_file_path}")
            except Exception as e:
                Logger.log_error(f"Ошибка при удалении временного файла при очистке: {str(e)}")

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
        
        # Инициализация менеджера синхронизации слоев QGIS
        self.qgis_sync_manager = QGISLayerSyncManager(self.dxf_tree_widget_handler)
        
        # Подключаем сигналы для синхронизации
        self.dxf_tree_widget_handler.tree_structure_created.connect(
            self.qgis_sync_manager.create_qgis_group_structure
        )
        self.dxf_tree_widget_handler.layer_check_changed.connect(
            self.qgis_sync_manager.sync_layer_from_plugin_to_qgis
        )
        # нажатие по кнопке export_to_db_button
        self.export_to_db_button.clicked.connect(self.export_to_db_button_click)
        
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

        if self.dxf_tree_widget_handler.get_selected_file_name() is None:
            QMessageBox.warning(None, self.lm.get_string("COMMON", "error"), 
                                   self.lm.get_string("MAIN_DIALOG", "no_file_selected"))
            return


        has_selection = len(self.dxf_handler.selected_entities[self.dxf_tree_widget_handler.get_selected_file_name()]) != self.dxf_handler.len_entities_file[self.dxf_tree_widget_handler.get_selected_file_name()]
        
        if has_selection:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setWindowTitle(self.lm.get_string("MAIN_DIALOG", "export_to_db"))
            msg_box.setText(self.lm.get_string("MAIN_DIALOG", "export_selected_question"))
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            
            result = msg_box.exec_()
            
            if result == QMessageBox.Cancel or result == QMessageBox.No:
                return
        
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
            files_result = get_all_dxf_files(username, password, uri.host(),
                                            uri.port(), uri.database())
            
            # Если get_all_dxf_files возвращает словарь, извлекаем список файлов
            if isinstance(files_result, dict):
                files = files_result.get('files', [])
            else:
                # Для обратной совместимости, если возвращается просто список
                files = files_result if files_result else []

            # Если файлы не найдены (даже после возможного диалога выбора схемы)
            if not files:
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

                # Проверяем наличие файла предпросмотра
                preview_path = os.path.join(self.plugin_root_dir, 'previews', f"{os.path.splitext(file['filename'])[0]}.svg")
                has_preview = os.path.exists(preview_path)
                
                # Создаем виджет предпросмотра если файл существует
                if has_preview:
                    preview_widget = self.preview_factory.create_preview_widget(
                        file['filename'],
                        self.plugin_root_dir,
                        self.show_full_preview
                    )
                    if preview_widget:
                        buttons_layout.addWidget(preview_widget)
                else:
                    # Добавляем кнопку для генерации предпросмотра
                    load_preview_button = QPushButton(self.lm.get_string("MAIN_DIALOG", "load_preview_button"))
                    load_preview_button.setFixedSize(100, 20)
                    load_preview_button.clicked.connect(
                        partial(self.generate_preview_for_file, conn_display_name, uri.database(), uri.host(), uri.port(), file['id'], file['filename']))
                    buttons_layout.addWidget(load_preview_button)

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
            if os.path.exists(preview_path):
                os.remove(preview_path)
            delete_dxf_file(saved_conn['username'], saved_conn['password'], host, port, database, file_id)
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
        # Показываем диалог выбора места импорта
        destination_dialog = ImportDestinationDialog(self)
        if destination_dialog.exec_() == QtWidgets.QDialog.Accepted:
            destination = destination_dialog.get_selected_destination()
            
            # Получаем подключение и файл из базы данных
            conn = self.connections_manager.get_connection(conn_display_name)
            if not conn:
                QMessageBox.warning(None, self.lm.get_string("COMMON", "error"), 
                                   self.lm.get_string("MAIN_DIALOG", "saved_credentials_error"))
                return
                
            file = get_dxf_file_by_id(conn['username'], conn['password'], host, port, dbname, file_id)
            if not file:
                QMessageBox.critical(None, self.lm.get_string("COMMON", "error"),
                                   self.lm.get_string("MAIN_DIALOG", "file_not_found_error", file_id))
                return
                
            file_content = file.file_content
            
            if destination == "qgis":
                # Импорт в QGIS через саб-плагин
                self._import_to_qgis(file_content, file_name)
            else:
                # Сохранение в файл на ПК
                self._save_to_file(file_content, file_name)

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
        self.setupUiText()

    def generate_preview_for_file(self, conn_display_name, database, host, port, file_id, filename):
        """
        Генерирует превью для файла из базы данных
        
        Args:
            conn_display_name: Имя подключения для получения сохраненных учетных данных
            database: Имя базы данных
            host: Хост базы данных
            port: Порт базы данных
            file_id: ID файла
            filename: Имя файла
        """
        try:
            # Получаем сохраненные учетные данные из ConnectionsManager
            conn = self.connections_manager.get_connection(conn_display_name)
            if not conn:
                QMessageBox.warning(None, self.lm.get_string("COMMON", "error"), 
                                   self.lm.get_string("MAIN_DIALOG", "saved_credentials_error"))
                return
            
            # Получаем файл из базы данных
            file = get_dxf_file_by_id(conn['username'], conn['password'], host, port, database, file_id)
            if not file:
                QMessageBox.warning(None, self.lm.get_string("COMMON", "error"),
                                   self.lm.get_string("MAIN_DIALOG", "file_not_found_error", file_id))
                return
            
            # Создаем и настраиваем диалог прогресса
            self.progress_dialog = QProgressDialog(self.lm.get_string("MAIN_DIALOG", "generating_preview"), None, 0, 0, self)
            self.progress_dialog.setWindowModality(Qt.WindowModal)
            self.progress_dialog.setWindowTitle(self.lm.get_string("MAIN_DIALOG", "preview_generation_title"))
            self.progress_dialog.setAutoClose(True)
            self.progress_dialog.setCancelButton(None)
            self.progress_dialog.setMinimumDuration(0)
            
            # Добавляем анимацию точек
            self.dots = 0
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_progress_dialog_text)
            self.timer.start(500)
            
            # Создаем поток для генерации превью
            self.preview_generator = PreviewGeneratorThread(
                self.dxf_handler,
                file.file_content,
                filename,
                self.plugin_root_dir
            )
            
            # Подключаем сигналы
            self.preview_generator.progress_update.connect(self.update_preview_progress)
            self.preview_generator.finished.connect(self.on_preview_generation_finished)
            
            # Запускаем поток
            self.preview_generator.start()
            
            # Показываем диалог прогресса
            self.progress_dialog.show()
            
        except Exception as e:
            Logger.log_error(f"Ошибка при начале генерации превью для файла {filename}: {str(e)}")
            QMessageBox.critical(None, self.lm.get_string("COMMON", "error"),
                                self.lm.get_string("MAIN_DIALOG", "preview_generation_error_with_details", str(e)))
    
    def update_preview_progress(self, percent, message):
        """
        Обновляет индикатор прогресса и сообщение для генерации превью
        
        :param percent: Процент выполнения (0-100)
        :param message: Сообщение о текущем этапе
        """
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.setLabelText(message)
            if percent > 0:  # Если передан конкретный процент
                self.progress_dialog.setMaximum(100)
                self.progress_dialog.setValue(percent)
            else:  # Если процент не определен, показываем бесконечный прогресс
                self.progress_dialog.setMaximum(0)
    
    def update_progress_dialog_text(self):
        """Обновление текста в окне прогресса (анимация точек)"""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.dots = (self.dots + 1) % 4
            # Получаем базовый текст без точек
            base_text = self.progress_dialog.labelText().rstrip('.')
            # Добавляем нужное количество точек
            animated_text = base_text + '.' * self.dots
            self.progress_dialog.setLabelText(animated_text)
    
    def on_preview_generation_finished(self, success, message, preview_path):
        """
        Обработка завершения генерации превью
        
        :param success: Флаг успешности операции
        :param message: Сообщение о результате
        :param preview_path: Путь к созданному файлу превью
        """
        # Останавливаем таймер анимации точек
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
        
        # Закрываем диалог прогресса
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
        
        if success:
            QMessageBox.information(None, self.lm.get_string("COMMON", "success"),
                                  self.lm.get_string("MAIN_DIALOG", "preview_generated_successfully", preview_path))
            
            # Обновляем отображение в дереве
            self.refresh_db_structure_treewidget()
        else:
            QMessageBox.warning(None, self.lm.get_string("COMMON", "error"),
                              self.lm.get_string("MAIN_DIALOG", "preview_generation_error_with_details", message))
        
        # Очищаем ссылку на поток
        if hasattr(self, 'preview_generator'):
            self.preview_generator.cleanup()  # Очищаем временные файлы если они остались
            self.preview_generator = None

    def _import_to_qgis(self, file_content, file_name):
        """
        Импорт DXF файла в QGIS через саб-плагин
        """
        try:
            # Создаем временный файл с содержимым DXF
            temp_file = tempfile.NamedTemporaryFile(suffix='.dxf', delete=False)
            temp_file.write(file_content)
            temp_file.close()
            
            # Импортируем саб-плагин AnotherDXF2Shape
            from ..plugins.dxf_tools.uiADXF2Shape import uiADXF2Shape
            
            # Создаем экземпляр саб-плагина (UI будет невидимым)
            dxf_plugin = uiADXF2Shape(self)
            
            # Вызываем функцию программного импорта
            success = dxf_plugin.import_dxf_programmatically(temp_file.name)

            
            if success:
                QMessageBox.information(None, self.lm.get_string("COMMON", "success"),
                                       self.lm.get_string("MAIN_DIALOG", "file_imported_to_qgis", file_name))
            # Удаляем временный файл
            os.unlink(temp_file.name)
            
        except Exception as e:
            Logger.log_message(self.lm.get_string("MAIN_DIALOG", "error_importing_to_qgis", file_name, str(e)))
            QMessageBox.critical(None, self.lm.get_string("COMMON", "error"),
                               self.lm.get_string("MAIN_DIALOG", "error_importing_to_qgis", file_name, str(e)))

    def _save_to_file(self, file_content, file_name):
        """
        Сохранение DXF файла на ПК
        """
        # Открываем диалоговое окно для выбора пути сохранения файла
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(None, self.lm.get_string("MAIN_DIALOG", "save_file_as"), 
                                                 f"{file_name}", "DXF файлы (*.dxf);;Все файлы (*)", options=options)
        
        if file_path:
            with open(file_path, 'wb') as f:
                try:
                    f.write(file_content)
                    QMessageBox.information(None, self.lm.get_string("COMMON", "success"),
                                            self.lm.get_string("MAIN_DIALOG", "file_saved_successfully", file_path))
                except Exception as e:
                    Logger.log_message(self.lm.get_string("MAIN_DIALOG", "error_saving_file", str(e)))
                    QMessageBox.critical(None, self.lm.get_string("COMMON", "error"),
                                        self.lm.get_string("MAIN_DIALOG", "error_saving_file", str(e)))
        else:
            QMessageBox.warning(None, self.lm.get_string("COMMON", "warning"), 
                               self.lm.get_string("MAIN_DIALOG", "file_path_error"))


    def setup_qgis_sync_for_imported_files(self, imported_files):
        """
        Настраивает синхронизацию для файлов, импортированных в QGIS через подплагин.
        
        Args:
            imported_files: Список путей к импортированным DXF файлам
        """
        try:
            if not imported_files:
                return
                
            # Получаем информацию о слоях из дерева плагина
            for file_path in imported_files:
                file_name = os.path.basename(file_path)
                
                # Проверяем, есть ли файл в дереве плагина
                if file_name in self.dxf_tree_widget_handler.tree_items:
                    file_data = self.dxf_tree_widget_handler.tree_items[file_name]
                    layers_dict = {}
                    
                    # Собираем информацию о слоях
                    for layer_name, layer_info in file_data.items():
                        if isinstance(layer_info, dict) and 'item' in layer_info:
                            layers_dict[layer_name] = {}  # Пустой словарь для совместимости
                    
                    # Создаем синхронизацию с QGIS
                    if layers_dict:
                        self.qgis_sync_manager.create_qgis_group_structure(file_name, layers_dict)
                        Logger.log_message(f"Настроена синхронизация для файла {file_name} с {len(layers_dict)} слоями")
                        
        except Exception as e:
            Logger.log_error(f"Ошибка настройки синхронизации QGIS: {str(e)}")
