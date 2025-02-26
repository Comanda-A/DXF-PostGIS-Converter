"""
Менеджер локализации для плагина
"""
from qgis.core import QgsSettings
from . import ru, en

class LocalizationManager:
    """
    Класс для управления локализацией плагина
    """
    _instance = None
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = LocalizationManager()
        return cls._instance
    
    def __init__(self):
        self.settings = QgsSettings()
        self.current_language = self.settings.value("DXFPostGISConverter/Language", "ru")
        self._load_language()
    
    def _load_language(self):
        """Загрузка языковых ресурсов"""
        if self.current_language == "ru":
            self.strings = ru
        elif self.current_language == "en":
            self.strings = en
        else:
            self.strings = ru
    
    def set_language(self, language_code):
        """Установка языка интерфейса"""
        self.current_language = language_code
        self.settings.setValue("DXFPostGISConverter/Language", language_code)
        self._load_language()
    
    def get_string(self, category, key, *args):
        """
        Получение строки по ключу с подстановкой параметров
        
        Args:
            category: Категория строки (например, MAIN_DIALOG)
            key: Ключ строки
            *args: Параметры для форматирования строки
        
        Returns:
            str: Локализованная строка
        """
        try:
            text = getattr(self.strings, category)[key]
            if args:
                return text.format(*args)
            return text
        except (AttributeError, KeyError):
            return f"[{category}.{key}]"  # Возвращаем ключ, если строка не найдена
