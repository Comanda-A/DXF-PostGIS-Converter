"""src.exporters.dxf_exporter

Facade exporter that keeps the historical DXFExporter API, while delegating
implementation to smaller classes (database export, selected entities export,
and background thread).
"""

from __future__ import annotations

from typing import Optional, Callable, Union

from ..dxf.dxf_handler import DXFHandler
from ..logger.logger import Logger

from .database_exporter import DXFDatabaseExporter
from .entities_exporter import DXFEntitiesExporter
from .export_thread import ExportThread


ExportResult = Union[bool, Optional[str]]


class DXFExporter:
    """Unified facade for DXF export operations.

    This class is used by GUI code. To avoid breaking existing integrations,
    its public methods remain stable and delegate work to specialized classes.
    """

    def __init__(self, dxf_handler: Optional[DXFHandler] = None):
        self.dxf_handler = dxf_handler
        self.logger = Logger
        self.db_exporter = DXFDatabaseExporter()
        self.entities_exporter = DXFEntitiesExporter(dxf_handler=dxf_handler)

    def export_from_database(
        self,
        username: str,
        password: str,
        host: str,
        port: str,
        dbname: str,
        file_id: int,
        destination: str = "file",
        file_name: Optional[str] = None,
    ) -> Optional[str]:
        """Export a DXF file stored in DB.

        Returns the created file path (for both "file" and "qgis" destinations)
        or None on failure/cancel.
        """
        return self.db_exporter.export_from_database(
            username=username,
            password=password,
            host=host,
            port=port,
            dbname=dbname,
            file_id=file_id,
            destination=destination,
            file_name=file_name,
        )

    def export_selected_entities(self, filename: str, output_file: str) -> bool:
        """Export selected entities of a loaded DXF into a new DXF file."""
        return self.entities_exporter.export_selected_entities(filename, output_file)

    def create_export_thread(self, export_function: Callable[[], ExportResult]) -> ExportThread:
        """Create a background thread for export execution."""
        return ExportThread(export_function)
