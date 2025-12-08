"""
DXF and Database Exporters
Handles exporting DXF entities and database files.
"""

import os
import tempfile
from typing import Optional
from ..dxf.dxf_handler import DXFHandler
from ..db.database import DatabaseManager
from ..logger.logger import Logger


class DXFExporter:
    """
    Unified exporter for DXF operations - both entity export and database file export.
    """

    def __init__(self, dxf_handler=None):
        """
        Initialize with optional DXF handler.

        Args:
            dxf_handler: DXFHandler instance (required for entity export operations)
        """
        self.dxf_handler = dxf_handler
        self.db_manager = DatabaseManager()
        self.logger = Logger

    def export_from_database(self, username: str, password: str, host: str, port: str, dbname: str,
                           file_id: int, destination: str = "file", file_name: str = None) -> Optional[str]:
        """
        Export DXF file from database to specified destination.

        Args:
            username: Database username
            password: Database password
            host: Database host
            port: Database port
            dbname: Database name
            file_id: File ID in database
            destination: "file" or "qgis"
            file_name: Optional filename for export

        Returns:
            Path to exported file if destination is "file", None otherwise
        """
        try:
            # Get file from database
            db_manager = DatabaseManager()
            file_record = db_manager.get_dxf_file_by_id(username, password, host, port, dbname, file_id)
            if not file_record:
                Logger.log_error(f"File with ID {file_id} not found in database")
                return None

            file_content = file_record.file_content
            filename = file_name or file_record.filename

            if destination == "qgis":
                # Return temp file path for QGIS import
                temp_dir = tempfile.gettempdir()
                temp_file_path = os.path.join(temp_dir, filename)

                with open(temp_file_path, 'wb') as f:
                    f.write(file_content)

                Logger.log_message(f"File {filename} exported to temp location for QGIS import")
                return temp_file_path

            else:  # destination == "file"
                # Save to user-specified location
                from qgis.PyQt.QtWidgets import QFileDialog
                from qgis.PyQt.QtCore import QCoreApplication

                file_path, _ = QFileDialog.getSaveFileName(
                    None,
                    QCoreApplication.translate("DXFExporter", "Save DXF File"),
                    filename,
                    "DXF files (*.dxf);;All files (*.*)"
                )

                if file_path:
                    with open(file_path, 'wb') as f:
                        f.write(file_content)

                    Logger.log_message(f"File {filename} exported to {file_path}")
                    return file_path
                else:
                    Logger.log_warning("File export cancelled by user")
                    return None

        except Exception as e:
            Logger.log_error(f"Error exporting file from database: {str(e)}")
            return None
