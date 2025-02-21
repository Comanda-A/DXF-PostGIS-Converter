import inspect
import os
from qgis.core import QgsMessageLog, Qgis

class Logger:
    @staticmethod
    def log_message(message, tag='DXF-PostGIS-Converter'):
        if not isinstance(message, str):
            message = str(message)
        QgsMessageLog.logMessage(message, tag, Qgis.Info)
        caller = inspect.stack()[1]
        filename = os.path.basename(caller.filename)
        location = f"\033[94m[{filename}:{caller.lineno}]\033[0m"
        message = f"{location} {message}"
        print(message)

    @staticmethod
    def log_warning(message, tag='DXF-PostGIS-Converter'):
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
