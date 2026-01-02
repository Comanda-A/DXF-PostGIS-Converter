# -*- coding: utf-8 -*-
"""
Resources - UI ресурсы (.ui файлы и т.д.).
"""

import os

# Путь к директории с .ui файлами (теперь в этой же папке)
UI_DIR = os.path.dirname(__file__)

def get_ui_path(filename: str) -> str:
    """
    Получить путь к .ui файлу.
    
    Args:
        filename: Имя файла (например, 'main_dialog.ui')
        
    Returns:
        Полный путь к файлу
    """
    return os.path.join(UI_DIR, filename)


# Пути к основным .ui файлам
MAIN_DIALOG_UI = get_ui_path('main_dialog.ui')
PROVIDERS_DIALOG_UI = get_ui_path('providers_dialog.ui')
