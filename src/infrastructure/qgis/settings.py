
from qgis.core import QgsSettings
from ...application.interfaces import ISettings

class Settings(ISettings):

    def __init__(self):
        self._settings = QgsSettings()
    
    def get_value(self, key: str, default=None, value_type=None):
        """Получить произвольное значение из настроек."""
        if value_type:
            return self._settings.value(key, default, type=value_type)
        return self._settings.value(key, default)
    
    def set_value(self, key: str, value) -> None:
        """Установить произвольное значение в настройки."""
        self._settings.setValue(key, value)
    
    def remove(self, key: str) -> None:
        """Удалить ключ из настроек."""
        self._settings.remove(key)
