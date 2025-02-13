from qgis.core import QgsMessageLog, Qgis

class Logger:
    @staticmethod
    def log_message(message, tag='QGIS'):
        if not isinstance(message, str):
            message = str(message)
        QgsMessageLog.logMessage(message, tag, Qgis.Info)

    @staticmethod
    def log_warning(message, tag='QGIS'):
        QgsMessageLog.logMessage(message, tag, Qgis.Warning)

    @staticmethod
    def log_error(message, tag='QGIS'):
        QgsMessageLog.logMessage(message, tag, Qgis.Critical)
