from PyQt5.QtCore import QThread, pyqtSignal

from ..db.database import export_dxf_to_database
from .log_capture import LogCapture
from ..localization.localization_manager import LocalizationManager
from ..logger.logger import Logger


class ExportThread(QThread):
    """
    Поток для выполнения экспорта данных в базу данных.
    Работает отдельно от основного потока интерфейса, чтобы не блокировать UI.    """
    finished = pyqtSignal(bool, str)  # Сигнал: успех/неуспех, сообщение

    progress_update = pyqtSignal(int, str)  # Сигнал обновления прогресса: процент, сообщение
    def __init__(self, username, password, address, port, dbname, dxf_handler, file_path,
                 mapping_mode, layer_schema='layer_schema', file_schema='file_schema',
                 export_layers_only=False, custom_filename=None, column_mapping_configs=None):
        """
        Инициализация потока экспорта.

        :param username: Имя пользователя для подключения к БД
        :param password: Пароль пользователя
        :param address: Адрес сервера БД
        :param port: Порт сервера БД
        :param dbname: Имя базы данных
        :param dxf_handler: Обработчик DXF-файлов
        :param file_path: Путь к DXF-файлу для экспорта
        :param mapping_mode: Режим маппирования слоев (always_overwrite, geometry, notes, both)
        :param layer_schema: Схема для размещения таблиц слоев
        :param file_schema: Схема для размещения таблицы файлов
        :param export_layers_only: Экспортировать только слои (без сохранения файла)
        :param custom_filename: Пользовательское название файла для сохранения в БД
        :param column_mapping_configs: Настройки сопоставления столбцов
        """
        super().__init__()
        self.username = username
        self.password = password
        self.address = address
        self.port = port
        self.dbname = dbname
        self.dxf_handler = dxf_handler
        self.file_path = file_path
        self.mapping_mode = mapping_mode
        self.layer_schema = layer_schema
        self.file_schema = file_schema
        self.export_layers_only = export_layers_only
        self.custom_filename = custom_filename
        self.column_mapping_configs = column_mapping_configs or {}
        self.lm = LocalizationManager.instance()

        # Создаем захватчик логов
        self.log_capture = LogCapture()
        self.log_capture.log_captured.connect(self.on_log_captured)

    def on_log_captured(self, message):
        """
        Обработчик захваченного лога - передаем его как прогресс
        """
        # Очищаем сообщение от лишних символов
        clean_message = message.strip()

        # Определяем процент прогресса на основе ключевых слов
        percent = 50  # Базовое значение прогресса

        if "подключение" in clean_message.lower() or "connecting" in clean_message.lower():
            percent = 10
        elif "создание" in clean_message.lower() or "creating" in clean_message.lower():
            percent = 20
        elif "обработка" in clean_message.lower() or "processing" in clean_message.lower():
            percent = 40
        elif "экспорт" in clean_message.lower() or "export" in clean_message.lower():
            percent = 60
        elif "сохранение" in clean_message.lower() or "saving" in clean_message.lower():
            percent = 80
        elif "завершен" in clean_message.lower() or "complete" in clean_message.lower():
            percent = 100

        self.progress_update.emit(percent, clean_message)

    def run(self):
        """
        Основной метод потока. Выполняет экспорт и отправляет сигнал о результате.        """
        try:
            # Начинаем захват логов
            self.log_capture.start_capture()

            Logger.log_message(self.lm.get_string("EXPORT_DIALOG", "export_thread_start"))
            Logger.log_message(f"Режим маппирования: {self.mapping_mode}")

            result = export_dxf_to_database(
                self.username,
                self.password,
                self.address,
                self.port,
                self.dbname,
                self.dxf_handler,
                self.file_path,
                self.mapping_mode,
                self.layer_schema,
                self.file_schema,
                self.export_layers_only,
                self.custom_filename,
                self.column_mapping_configs
            )

            # Останавливаем захват логов
            self.log_capture.stop_capture()

            if result:
                Logger.log_message(self.lm.get_string("EXPORT_DIALOG", "export_thread_success"))
                self.finished.emit(True, self.lm.get_string("EXPORT_DIALOG", "export_thread_complete"))
            else:
                Logger.log_error("Экспорт не был завершен успешно")
                self.finished.emit(False, self.lm.get_string("EXPORT_DIALOG", "export_thread_failed"))
        except Exception as e:
            # Останавливаем захват логов в случае ошибки
            self.log_capture.stop_capture()
            Logger.log_error(f"Ошибка при экспорте: {str(e)}")
            self.finished.emit(False, str(e))
