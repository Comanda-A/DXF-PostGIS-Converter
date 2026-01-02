"""src.exporters.database_exporter

DXF export from PostgreSQL/PostGIS storage.

This module isolates DB retrieval and file materialization logic from GUI code.
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

from ..infrastructure.database import DatabaseConnection, DxfRepository
from ..logger.logger import Logger


class DXFDatabaseExporter:
    """Exports DXF files stored in the database."""

    def __init__(self, connection: Optional[DatabaseConnection] = None, repository: Optional[DxfRepository] = None):
        self._connection = connection or DatabaseConnection.instance()
        self._repository = repository or DxfRepository(self._connection)
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
            # Подключаемся к базе данных
            if not self._connection.connect(username, password, host, port, dbname):
                Logger.log_error(f"Failed to connect to database")
                return None
            
            session = self._connection.get_session()
            if session is None:
                Logger.log_error("Failed to get database session")
                return None
            
            # Получаем файл по ID (пробуем разные схемы)
            file_record = None
            for schema in ['file_schema', 'public']:
                file_record = self._repository.get_file_by_id(session, file_id, schema)
                if file_record:
                    break
            
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
