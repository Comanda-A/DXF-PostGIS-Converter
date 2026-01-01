"""src.exporters.database_exporter

DXF export from PostgreSQL/PostGIS storage.

This module isolates DB retrieval and file materialization logic from GUI code.
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

from ..db.database import DatabaseManager
from ..logger.logger import Logger


class DXFDatabaseExporter:
    """Exports DXF files stored in the database."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.logger = Logger

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
        """Export DXF file content from DB.

        Args:
            destination: "file" or "qgis".

        Returns:
            File path (temp path for "qgis" destination, selected path for "file")
            or None when not exported.
        """
        try:
            file_record = self.db_manager.get_dxf_file_by_id(username, password, host, port, dbname, file_id)
            if not file_record:
                Logger.log_error(f"File with ID {file_id} not found in database")
                return None

            file_content = file_record.file_content
            filename = file_name or file_record.filename

            if destination == "qgis":
                temp_dir = tempfile.gettempdir()
                temp_file_path = os.path.join(temp_dir, filename)
                with open(temp_file_path, 'wb') as f:
                    f.write(file_content)
                Logger.log_message(f"File {filename} exported to temp location for QGIS import")
                return temp_file_path

            if destination != "file":
                Logger.log_error(f"Unsupported export destination: {destination}")
                return None

            from qgis.PyQt.QtWidgets import QFileDialog
            from qgis.PyQt.QtCore import QCoreApplication

            file_path, _ = QFileDialog.getSaveFileName(
                None,
                QCoreApplication.translate("DXFExporter", "Save DXF File"),
                filename,
                "DXF files (*.dxf);;All files (*.*)"
            )

            if not file_path:
                Logger.log_warning("File export cancelled by user")
                return None

            with open(file_path, 'wb') as f:
                f.write(file_content)

            Logger.log_message(f"File {filename} exported to {file_path}")
            return file_path

        except Exception as e:
            Logger.log_error(f"Error exporting file from database: {str(e)}")
            return None
