# -*- coding: utf-8 -*-
"""
Migration Bridge - позволяет переключаться между старой и новой версией.

Для использования новой рефакторированной версии:
1. Установите переменную окружения: USE_REFACTORED_PLUGIN=1
2. Или измените USE_REFACTORED = True ниже

По умолчанию используется старая версия для обратной совместимости.
"""

import os

# Флаг использования рефакторированной версии
USE_REFACTORED = os.environ.get('USE_REFACTORED_PLUGIN', '0') == '1'


def get_plugin_class():
    """
    Возвращает класс плагина в зависимости от режима.
    
    Returns:
        Класс плагина (старый или рефакторированный)
    """
    if USE_REFACTORED:
        from .dxf_postgis_converter_refactored import DxfPostGISConverterRefactored
        return DxfPostGISConverterRefactored
    else:
        from .dxf_postgis_converter import DxfPostGISConverter
        return DxfPostGISConverter


def get_import_dialog_class():
    """
    Возвращает класс диалога импорта.
    
    Returns:
        Класс диалога (старый или рефакторированный)
    """
    if USE_REFACTORED:
        from .gui.import_dialog_refactored import ImportDialogRefactored
        return ImportDialogRefactored
    else:
        from .gui.import_dialog import ImportDialog
        return ImportDialog


def get_main_dialog_class():
    """
    Возвращает класс главного диалога.
    
    Returns:
        Класс диалога (старый или рефакторированный)
    """
    if USE_REFACTORED:
        from .gui.main_dialog_refactored import ConverterDialogRefactored
        return ConverterDialogRefactored
    else:
        from .gui.main_dialog import ConverterDialog
        return ConverterDialog
