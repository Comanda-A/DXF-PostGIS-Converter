from qgis.core import QgsMessageLog, Qgis

class Logger:
    @staticmethod
    def log_message(message, tag='QGIS'):
        QgsMessageLog.logMessage(message, tag, Qgis.Info)
