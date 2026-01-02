# -*- coding: utf-8 -*-
"""
Migration Bridge - устаревший модуль для обратной совместимости.

После удаления старой реализации этот модуль сохранён только для 
обратной совместимости с кодом, который может его использовать.
Рекомендуется импортировать классы напрямую из соответствующих модулей.
"""


def get_plugin_class():
    """
    Возвращает класс плагина.
    
    Returns:
        DxfPostGISConverter
    """
    from .dxf_postgis_converter import DxfPostGISConverter
    return DxfPostGISConverter


def get_import_dialog_class():
    """
    Возвращает класс диалога импорта.
    
    Returns:
        ImportDialog
    """
    from .gui.import_dialog import ImportDialog
    return ImportDialog


def get_main_dialog_class():
    """
    Возвращает класс главного диалога.
    
    Returns:
        ConverterDialog
    """
    from .gui.main_dialog import ConverterDialog
    return ConverterDialog
