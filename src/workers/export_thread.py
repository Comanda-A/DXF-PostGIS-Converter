# -*- coding: utf-8 -*-
"""
Export Thread - фоновый поток для операций экспорта.

Выполняет экспорт из PostgreSQL/PostGIS в DXF в отдельном потоке,
чтобы не блокировать UI.
"""

from __future__ import annotations

from typing import Callable, Union, Tuple

from .base_thread import BaseWorkerThread
from ..logger.logger import Logger


ExportFnResult = Union[bool, str, None]


class ExportThread(BaseWorkerThread):
    """
    Поток для выполнения экспорта DXF данных.
    
    Наследует BaseWorkerThread, которая обеспечивает:
    - Захват логов через LogCapture
    - Определение прогресса по ключевым словам
    - Сигналы finished и progress_update
    """

    def __init__(self, export_function: Callable[[], ExportFnResult]):
        """
        Args:
            export_function: Функция, выполняющая экспорт
        """
        super().__init__()
        self.export_function = export_function

    def execute(self) -> Tuple[bool, str]:
        """Выполняет экспорт."""
        Logger.log_message("Начало экспорта DXF")
        result = self.export_function()
        success, message = self._normalize_result(result)
        
        if success:
            Logger.log_message("Экспорт DXF успешно завершен")
        else:
            Logger.log_error("Экспорт DXF не был завершен успешно")
        
        return success, message

    @staticmethod
    def _normalize_result(result: ExportFnResult) -> Tuple[bool, str]:
        """
        Нормализовать результат функции экспорта.
        
        Args:
            result: Результат (bool, str или None)
            
        Returns:
            Кортеж (success, message)
        """
        if isinstance(result, str):
            if result:
                return True, result
            return False, ""
        if result is True:
            return True, ""
        return False, ""
