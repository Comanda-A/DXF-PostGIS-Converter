# -*- coding: utf-8 -*-
"""
DXF Entities Exporter - экспорт выбранных DXF сущностей.

Экспортирует выбранные сущности из загруженного DXF файла в новый файл.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ...logger.logger import Logger

if TYPE_CHECKING:
    from ..dxf.dxf_handler import DXFHandler


class DXFEntitiesExporter:
    """
    Экспортирует выбранные сущности из загруженного DXF файла.
    
    Использует DXFHandler для работы с DXF документами.
    """

    def __init__(self, dxf_handler: Optional['DXFHandler'] = None):
        """
        Args:
            dxf_handler: Обработчик DXF файлов для извлечения сущностей
        """
        self.dxf_handler = dxf_handler
        self.logger = Logger

    def export_selected_entities(self, filename: str, output_file: str) -> bool:
        """
        Экспорт выбранных сущностей DXF файла в выходной файл.
        
        Args:
            filename: Имя исходного DXF файла (ключ в dxf_handler)
            output_file: Путь для сохранения нового DXF файла
            
        Returns:
            True если экспорт успешен
        """
        if not self.dxf_handler:
            Logger.log_error("DXFHandler is required for exporting selected entities")
            return False

        try:
            return bool(self.dxf_handler.save_selected_entities(filename, output_file))
        except Exception as e:
            Logger.log_error(f"Ошибка при экспорте выбранных сущностей: {str(e)}")
            return False
