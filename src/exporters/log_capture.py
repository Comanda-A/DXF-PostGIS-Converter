"""
Log capture utilities for export operations.
"""

from PyQt5.QtCore import QObject, pyqtSignal
from qgis.core import Qgis, QgsApplication


class LogCapture(QObject):
    """
    Класс для перехвата логов из QgsMessageLog и передачи их в progress_update
    """
    log_captured = pyqtSignal(str)  # Сигнал для передачи захваченного лога

    def __init__(self):
        super().__init__()
        self.is_capturing = False
        # Подключаемся к сигналу QgsMessageLog через экземпляр
        QgsApplication.messageLog().messageReceived.connect(self.on_message_received)

    def start_capture(self):
        """Начать захват логов"""
        self.is_capturing = True

    def stop_capture(self):
        """Остановить захват логов"""
        self.is_capturing = False

    def on_message_received(self, message, tag, level):
        """
        Обработчик получения нового сообщения в лог
        """
        if self.is_capturing and tag == 'DXF-PostGIS-Converter':
            # Передаем только информационные сообщения как прогресс
            if level == Qgis.Info:
                self.log_captured.emit(message)
