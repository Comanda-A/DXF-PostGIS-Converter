# -*- coding: utf-8 -*-
"""
Export Thread - фоновый поток для операций экспорта.

Выполняет экспорт из PostgreSQL/PostGIS в DXF в отдельном потоке,
чтобы не блокировать UI.
"""

from __future__ import annotations

from typing import Callable, Optional, Union, Tuple

from PyQt5.QtCore import QThread, pyqtSignal

from ..logger.log_capture import LogCapture
from ..localization.localization_manager import LocalizationManager
from ..logger.logger import Logger


ExportFnResult = Union[bool, str, None]


class ExportThread(QThread):
    """
    Поток для выполнения экспорта DXF данных.
    
    Работает отдельно от основного потока интерфейса, чтобы не блокировать UI.
    """

    finished = pyqtSignal(bool, str)  # Сигнал: успех/неуспех, сообщение
    progress_update = pyqtSignal(int, str)  # Сигнал прогресса: процент, сообщение

    def __init__(self, export_function: Callable[[], ExportFnResult]):
        """
        Инициализация потока экспорта.
        
        Args:
            export_function: Функция, выполняющая экспорт
        """
        super().__init__()
        self.export_function = export_function
        self.lm = LocalizationManager.instance()

        self.log_capture = LogCapture()
        self.log_capture.log_captured.connect(self.on_log_captured)

    def on_log_captured(self, message: str):
        """
        Обработчик захваченного лога - передаем его как прогресс.
        """
        clean_message = (message or "").strip()

        percent = 50
        lowered = clean_message.lower()

        if "подключ" in lowered or "connecting" in lowered:
            percent = 10
        elif "получ" in lowered or "извлеч" in lowered or "fetch" in lowered or "get" in lowered:
            percent = 30
        elif "создан" in lowered or "генер" in lowered or "build" in lowered or "generate" in lowered:
            percent = 60
        elif "сохран" in lowered or "saving" in lowered or "save" in lowered:
            percent = 80
        elif "заверш" in lowered or "complete" in lowered or "готов" in lowered:
            percent = 100

        self.progress_update.emit(percent, clean_message)

    def run(self):
        """
        Основной метод потока. Выполняет экспорт и отправляет сигнал о результате.
        """
        try:
            self.log_capture.start_capture()
            Logger.log_message("Начало экспорта DXF")

            result = self.export_function()

            self.log_capture.stop_capture()

            success, message = self._normalize_result(result)
            if success:
                Logger.log_message("Экспорт DXF успешно завершен")
            else:
                Logger.log_error("Экспорт DXF не был завершен успешно")

            self.finished.emit(success, message)

        except Exception as e:
            self.log_capture.stop_capture()
            Logger.log_error(f"Ошибка при экспорте: {str(e)}")
            self.finished.emit(False, str(e))

    @staticmethod
    def _normalize_result(result: ExportFnResult) -> Tuple[bool, str]:
        """
        Нормализовать результат функции экспорта.
        
        Args:
            result: Результат (bool, str или None)
            
        Returns:
            Кортеж (success, message)
        """
        if isinstance(result, str):
            if result:
                return True, result
            return False, ""
        if result is True:
            return True, ""
        return False, ""
