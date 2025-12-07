"""
DXF to DXF Exporter
Handles exporting selected DXF entities to new DXF files.
"""

from typing import Optional
from ..dxf.dxf_exporter import DXFExporter as OriginalDXFExporter
from ..logger.logger import Logger


class DXFEntityExporter:
    """
    Handles exporting selected DXF entities to new DXF files.
    """

    def __init__(self, dxf_handler):
        """
        Initialize with DXF handler.

        Args:
            dxf_handler: DXFHandler instance
        """
        self.dxf_handler = dxf_handler
        self.original_exporter = OriginalDXFExporter(dxf_handler)
        self.logger = Logger

    def export_selected_entities(self, filename: str, output_file: str) -> bool:
        """
        Export selected entities from DXF file to new DXF file.

        Args:
            filename: Source DXF filename
            output_file: Output DXF file path

        Returns:
            True if successful, False otherwise
        """
        try:
            return self.original_exporter.export_selected_entities(filename, output_file)
        except Exception as e:
            Logger.log_error(f"Error exporting selected entities: {str(e)}")
            return False
