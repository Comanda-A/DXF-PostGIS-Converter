"""src.exporters.entities_exporter

Export of selected DXF entities (in-memory DXF) to a new DXF file.
"""

from __future__ import annotations

from typing import Optional

from ..dxf.dxf_handler import DXFHandler
from ..logger.logger import Logger


class DXFEntitiesExporter:
    """Exports selected entities from a loaded DXF file."""

    def __init__(self, dxf_handler: Optional[DXFHandler] = None):
        self.dxf_handler = dxf_handler
        self.logger = Logger

    def export_selected_entities(self, filename: str, output_file: str) -> bool:
        """Export selected entities of the given DXF file to output_file."""
        if not self.dxf_handler:
            Logger.log_error("DXFHandler is required for exporting selected entities")
            return False

        try:
            return bool(self.dxf_handler.save_selected_entities(filename, output_file))
        except Exception as e:
            Logger.log_error(f"Ошибка при экспорте выбранных сущностей: {str(e)}")
            return False
