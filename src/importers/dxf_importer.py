"""
DXF to Database Importer
Handles importing DXF files into PostGIS database.
"""

from typing import Optional, Dict, List
from ..db.database import export_dxf_to_database, _connect_to_database, ensure_postgis_extension
from ..logger.logger import Logger


class DXFImporter:
    """
    Handles importing DXF files into PostGIS database.
    """

    def __init__(self):
        self.logger = Logger

    def import_dxf_to_database(self, username: str, password: str, host: str, port: str, dbname: str,
                              dxf_handler, file_path: str, mapping_mode: str = "always_overwrite",
                              layer_schema: str = 'layer_schema', file_schema: str = 'file_schema',
                              export_layers_only: bool = False, custom_filename: str = None,
                              column_mapping_configs: dict = None) -> bool:
        """
        Import DXF file into PostGIS database.

        Args:
            username: Database username
            password: Database password
            host: Database host
            port: Database port
            dbname: Database name
            dxf_handler: DXFHandler instance
            file_path: Path to DXF file
            mapping_mode: Column mapping mode
            layer_schema: Layer schema name
            file_schema: File schema name
            export_layers_only: Whether to export layers only
            custom_filename: Custom filename for DB
            column_mapping_configs: Column mapping configurations

        Returns:
            True if successful, False otherwise
        """
        try:
            # Test connection and ensure PostGIS
            session = _connect_to_database(username, password, host, port, dbname)
            if session is None:
                Logger.log_error("Failed to connect to database")
                return False

            if not ensure_postgis_extension(session):
                Logger.log_error("PostGIS extension not available")
                return False

            session.close()

            # Use the existing export_dxf_to_database function (which is actually import)
            return export_dxf_to_database(
                username=username,
                password=password,
                host=host,
                port=port,
                dbname=dbname,
                dxf_handler=dxf_handler,
                file_path=file_path,
                mapping_mode=mapping_mode,
                layer_schema=layer_schema,
                file_schema=file_schema,
                export_layers_only=export_layers_only,
                custom_filename=custom_filename,
                column_mapping_configs=column_mapping_configs
            )

        except Exception as e:
            Logger.log_error(f"Error importing DXF to database: {str(e)}")
            return False
