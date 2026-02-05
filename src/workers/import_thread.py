# -*- coding: utf-8 -*-
"""
Import Thread - фоновый поток для операций импорта.

Выполняет импорт DXF в PostgreSQL/PostGIS в отдельном потоке,
чтобы не блокировать UI.
"""

from typing import Callable, Tuple

from .base_thread import BaseWorkerThread
from ..logger.logger import Logger


class ImportThread(BaseWorkerThread):
    """
    Поток для выполнения импорта DXF данных в базу данных.
    
    Наследует BaseWorkerThread, которая обеспечивает:
    - Захват логов через LogCapture
    - Определение прогресса по ключевым словам
    - Сигналы finished и progress_update
    """
    
    def __init__(self, import_function: Callable[[], bool]):
        """
        Args:
            import_function: Функция, выполняющая импорт и возвращающая bool результат
        """
        super().__init__()
        self.import_function = import_function

    def execute(self) -> Tuple[bool, str]:
        """Выполняет импорт."""
        Logger.log_message("Начало импорта DXF файла в базу данных")
        result = self.import_function()
        
        if result:
            Logger.log_message("Импорт DXF файла успешно завершен")
            return True, "Импорт DXF файла в базу данных завершен успешно"
        else:
            Logger.log_error("Импорт не был завершен успешно")
            return False, "Ошибка при импорте DXF файла в базу данных"
