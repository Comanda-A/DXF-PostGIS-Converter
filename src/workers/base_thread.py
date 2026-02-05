# -*- coding: utf-8 -*-
"""
Base Thread - базовый класс для фоновых потоков с общей логикой.

Выносит общий функционал:
- Захват логов через LogCapture
- Определение прогресса по ключевым словам
- Шаблон start/stop capture
"""

from PyQt5.QtCore import QThread, pyqtSignal
from typing import List, Tuple

from ..logger.log_capture import LogCapture
from ..logger.logger import Logger


# Правила определения процента прогресса по ключевым словам в логе.
# Формат: (процент, [список_ключевых_слов])
DEFAULT_PROGRESS_KEYWORDS: List[Tuple[int, List[str]]] = [
    (10, ["подключ", "connecting", "connect"]),
    (20, ["создание", "creating"]),
    (30, ["получ", "извлеч", "fetch", "get"]),
    (40, ["обработка", "processing"]),
    (60, ["экспорт", "export", "создан", "генер", "build", "generate"]),
    (80, ["сохранение", "сохран", "saving", "save"]),
    (100, ["завершен", "заверш", "complete", "готов"]),
]


class BaseWorkerThread(QThread):
    """
    Базовый класс для фоновых потоков с поддержкой захвата логов.
    
    Предоставляет:
    - Настройку LogCapture с автоматическим определением прогресса
    - Шаблонный метод run() с start/stop capture
    - Единые сигналы finished и progress_update
    """

    finished = pyqtSignal(bool, str)
    progress_update = pyqtSignal(int, str)

    def __init__(self):
        super().__init__()
        self.log_capture = LogCapture()
        self.log_capture.log_captured.connect(self._on_log_captured)

    def _on_log_captured(self, message: str):
        """
        Обработчик захваченного лога — определяет прогресс по ключевым словам.
        """
        clean_message = (message or "").strip()
        lowered = clean_message.lower()

        percent = 50  # Значение по умолчанию
        for target_percent, keywords in DEFAULT_PROGRESS_KEYWORDS:
            if any(kw in lowered for kw in keywords):
                percent = target_percent
                break

        self.progress_update.emit(percent, clean_message)

    def run(self):
        """Шаблонный метод — захватывает логи и делегирует execute()."""
        try:
            self.log_capture.start_capture()
            success, message = self.execute()
            self.log_capture.stop_capture()
            self.finished.emit(success, message)
        except Exception as e:
            self.log_capture.stop_capture()
            Logger.log_error(f"Ошибка в потоке: {str(e)}")
            self.finished.emit(False, str(e))

    def execute(self) -> Tuple[bool, str]:
        """
        Переопределите этот метод в подклассах.
        
        Returns:
            Кортеж (success: bool, message: str)
        """
        raise NotImplementedError("Подклассы должны реализовать execute()")
