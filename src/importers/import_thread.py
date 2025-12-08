from PyQt5.QtCore import QThread, pyqtSignal
from typing import Callable

from ..exporters.log_capture import LogCapture
from ..localization.localization_manager import LocalizationManager
from ..logger.logger import Logger


class ImportThread(QThread):
    """
    Поток для выполнения импорта DXF данных в базу данных.
    Работает отдельно от основного потока интерфейса, чтобы не блокировать UI.    """
    finished = pyqtSignal(bool, str)  # Сигнал: успех/неуспех, сообщение

    progress_update = pyqtSignal(int, str)  # Сигнал обновления прогресса: процент, сообщение
    def __init__(self, import_function: Callable[[], bool]):
        """
        Инициализация потока импорта.

        :param import_function: Функция, выполняющая импорт и возвращающая bool результат
        """
        super().__init__()
        self.import_function = import_function
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
        Основной метод потока. Выполняет импорт и отправляет сигнал о результате.        """
        try:
            # Начинаем захват логов
            self.log_capture.start_capture()

            Logger.log_message("Начало импорта DXF файла в базу данных")

            # Выполняем функцию импорта
            result = self.import_function()

            # Останавливаем захват логов
            self.log_capture.stop_capture()

            if result:
                Logger.log_message("Импорт DXF файла успешно завершен")
                self.finished.emit(True, "Импорт DXF файла в базу данных завершен успешно")
            else:
                Logger.log_error("Импорт не был завершен успешно")
                self.finished.emit(False, "Ошибка при импорте DXF файла в базу данных")
        except Exception as e:
            # Останавливаем захват логов в случае ошибки
            self.log_capture.stop_capture()
            Logger.log_error(f"Ошибка при импорте: {str(e)}")
            self.finished.emit(False, str(e))
