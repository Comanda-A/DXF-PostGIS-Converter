
from types import ModuleType
from typing import Dict

from ....i18n import ru, en

from ...application.interfaces import ILocalization, ISettings, ILogger
from ...application.events import IAppEvents


class Localization(ILocalization):
    """Загружает переводы из JSON файлов"""
    
    _LANGUAGE_KEY = "Language"          # Ключ в настройках
    _available_languages = [ru, en]     # Список модулей языков
    
    def __init__(self, settings: ISettings, logger: ILogger, app_events: IAppEvents):
        self._settings = settings
        self._logger = logger
        self._app_events = app_events
        self._module: ModuleType = None     # Модуль языка
        
        # Устанавливаем начальный язык
        initial_language = self._settings.get_value(self._LANGUAGE_KEY, default="ru")
        self.set_language_by_code(initial_language)

    @property
    def language_code(self) -> str:
        if self._module:
            return self._module.CONFIG["code"]
        return ""
    
    @property
    def language_name(self) -> str:
        """Название текущего языка"""
        if self._module:
            return self._module.CONFIG["name"]
        return ""
    
    @property
    def available_languages(self) -> Dict[str, str]:
        """Возвращает словарь доступных языков в формате {код: название}"""
        return {lang.CONFIG["code"]: lang.CONFIG["name"] for lang in self._available_languages}

    def set_language_by_name(self, name: str, default: str = "") -> bool:
        """Установка языка интерфейса"""
        supported_names = {lang.CONFIG["name"]: lang.CONFIG["code"] for lang in self._available_languages}

        if name in supported_names:
            return self.set_language_by_code(supported_names[name])
        elif default and default in supported_names:
            return self.set_language_by_code(supported_names[default])
        
        self._logger.error(f"Unsupported language: {name}. Available: {supported_names.keys()}")
        return False
        
    def set_language_by_code(self, code: str, default: str = "") -> bool:
        """Установка языка интерфейса"""
        supported_codes = {lang.CONFIG["code"]: lang for lang in self._available_languages}

        if code in supported_codes:
            self._module = supported_codes[code]
        elif default and default in supported_codes:
            self._module = supported_codes[default]
        else:
            self._logger.error(f"Unsupported language: {code}. Available: {supported_codes.keys()}")
            return False

        self._settings.set_value(self._LANGUAGE_KEY, self.language_code)
        self._app_events.on_language_changed.emit(self.language_code)

        self._logger.message(f"Language installed: {self.language_code}")
        return True
    
    def tr(self, category, key, *args):
        """Получение локализованной строки по категории и ключу"""
        try:
            # Получаем словарь категории
            category_dict = getattr(self._module, category)
            
            # Получаем строку по ключу
            text = category_dict[key]
            
            # Форматируем строку если есть аргументы
            if args:
                return text.format(*args)
            return text
            
        except (KeyError, AttributeError) as e:
            self._logger.error(f"LocalizationManager | Error getting localized string: category='{category}', key='{key}', error='{str(e)}'")
            return f"[{category}.{key}]"
        except Exception as e:
            self._logger.error(f"LocalizationManager | Unexpected error while getting string '{category}.{key}': {str(e)}")
            return f"[{category}.{key}]"

    def get_all_translations(self, category: str) -> Dict[str, str]:
        try:
            # Получаем словарь категории
            category_dict = getattr(self._module, category)
            
            # Проверяем, что это действительно словарь
            if not isinstance(category_dict, dict):
                self._logger.error(f"LocalizationManager | Category '{category}' is not a dictionary")
                return {}
                
            return category_dict.copy()  # Возвращаем копию
            
        except AttributeError:
            self._logger.error(f"LocalizationManager | Category '{category}' not found in current language module")
            return {}
        except Exception as e:
            self._logger.error(f"LocalizationManager | Unexpected error getting all translations for category '{category}': {str(e)}")
            return {}