
import inject

from typing import Any
from ...application.interfaces import ILocalization, ILogger

class DialogTranslator:
    """Переводчик диалоговых окон"""
    
    # Словарь соответствия суффиксов типов виджетов и их атрибутов для установки текста
    _WIDGET_TEXT_ATTRIBUTES = {
        "_button": "setText",           # для кнопок
        "_label": "setText",            # для обычных надписей
        "_check": "setText",            # для чекбоксов
        "_group": "setTitle",           # для групп
        "_edit": "setPlaceholderText"   # для полей ввода
    }

    @inject.autoparams
    def __init__(self, localization: ILocalization = None, logger: ILogger = None):
        self._localization = localization
        self._logger = logger

    def translate(self, dialog: Any, category: str) -> None:
        """Переводит все элементы диалогового окна"""
        
        if not self._localization or not self._logger:
            return
        
        # Получаем все переводы для указанной категории
        translations = self._localization.get_all_translations(category)
        
        if not translations:
            self._logger.error(f"DialogTranslator | No translations found for category '{category}'")
            return
        
        # Заголовок окна
        if "dialog_title" in translations:
            if hasattr(dialog, "setWindowTitle"):
                try:
                    dialog.setWindowTitle(translations["dialog_title"])
                except Exception as e:
                    self._logger.error(f"DialogTranslator | Error translating window title: {str(e)}")
            del translations["dialog_title"]
        
        # Проходим по остальным переводам
        for name, text in translations.items():                
            # Проверяем, есть ли атрибут с таким именем в диалоге
            if hasattr(dialog, name):
                attr = getattr(dialog, name)
                # Определяем тип виджета по суффиксу
                for suffix, method_name in DialogTranslator._WIDGET_TEXT_ATTRIBUTES.items():
                    if name.endswith(suffix):
                        try:
                            set_text_method = getattr(attr, method_name)
                            set_text_method(text)
                        except Exception as e:
                            self._logger.error(f"DialogTranslator | Error translating '{name}': {str(e)}")
                        break
