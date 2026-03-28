
import inject

from qgis.core import QgsMessageLog, Qgis
from ...application.interfaces import ILogger, ISettings

class Logger(ILogger):
    
    _LOGGER_KEY = "Logger"  # Ключ в настройках

    @inject.autoparams
    def __init__(self, settings: ISettings):
        self._settings = settings
        self._enabled = settings.get_value(self._LOGGER_KEY, default=True, value_type=bool)
    
    def is_enabled(self):
        return self._enabled

    def set_enabled(self, enabled):
        self._enabled = enabled
        self._settings.set_value(self._LOGGER_KEY, enabled)
    
    def message(self, message, tag='DXF-PostGIS-Converter'):   
        if self._enabled:
            QgsMessageLog.logMessage(message, tag, Qgis.Info)

    @staticmethod
    def warning(message, tag='DXF-PostGIS-Converter'):
        QgsMessageLog.logMessage(message, tag, Qgis.Warning)

    @staticmethod
    def error(message, tag='DXF-PostGIS-Converter'):
        QgsMessageLog.logMessage(message, tag, Qgis.Critical)