import inspect
import os
from qgis.core import QgsMessageLog, Qgis, QgsSettings

class Logger:
    # Переменная класса для управления логированием
    _logging_enabled = None
    
    @classmethod
    def is_logging_enabled(cls):
        """
        Проверяет, включено ли логирование в настройках
        """
        if cls._logging_enabled is None:
            # Инициализируем из QSettings, если ещё не установлено
            settings = QgsSettings()
            cls._logging_enabled = settings.value("DXFPostGISConverter/EnableLogging", False, type=bool)
        return cls._logging_enabled
    
    @classmethod
    def set_logging_enabled(cls, enabled):
        """
        Устанавливает состояние логирования
        """
        cls._logging_enabled = enabled
    
    @staticmethod
    def log_message(message, tag='DXF-PostGIS-Converter'):
        if not isinstance(message, str):
            message = str(message)      
        if Logger.is_logging_enabled():
            QgsMessageLog.logMessage(message, tag, Qgis.Info)
            caller = inspect.stack()[1]
            filename = os.path.basename(caller.filename)
            location = f"\033[94m[{filename}:{caller.lineno}]\033[0m"
            message = f"{location} {message}"
            print(message)

    @staticmethod
    def log_warning(message, tag='DXF-PostGIS-Converter'):
        # Всегда логируем в журнал QGIS
        QgsMessageLog.logMessage(message, tag, Qgis.Warning)
        caller = inspect.stack()[1]
        filename = os.path.basename(caller.filename)
        location = f"\033[94m[{filename}:{caller.lineno}]\033[0m"
        message = f"{location} \033[93m{message}\033[0m"
        print(message)

    @staticmethod
    def log_error(message, tag='DXF-PostGIS-Converter'):
        QgsMessageLog.logMessage(message, tag, Qgis.Critical)
        caller = inspect.stack()[1]
        filename = os.path.basename(caller.filename)
        location = f"\033[94m[{filename}:{caller.lineno}]\033[0m"
        message = f"{location} \033[91m{message}\033[0m"
        print(message)
