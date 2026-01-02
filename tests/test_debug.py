# -*- coding: utf-8 -*-
"""Debug test to find the issue with import."""
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.domain.dxf import DxfDocument
from src.domain.models import ImportConfig
from src.application.import_service import ImportService
from src.application.settings_service import ConnectionSettings
from src.infrastructure.database import DatabaseConnection, DxfRepository


def test_import():
    """Test the full import flow with detailed debugging."""
    dxf_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dxf_examples')
    dxf_file = os.path.join(dxf_dir, 'ex1.dxf')
    
    print(f"Testing file: {dxf_file}")
    print(f"File exists: {os.path.exists(dxf_file)}")
    
    # Test connection settings
    conn_settings = ConnectionSettings(
        host='localhost',
        port='5432',
        database='test_dxf',
        username='postgres',
        password='123'
    )
    
    print(f"\nConnection settings: {conn_settings}")
    print(f"Is configured: {conn_settings.is_configured}")
    
    # Test database connection
    db_conn = DatabaseConnection.instance()
    session = db_conn.connect(conn_settings)
    
    if session:
        print("Database connected successfully!")
    else:
        print("Failed to connect to database")
        return
    
    # Test schema creation
    print("\n=== Testing Schema and Table Creation ===")
    layer_schema = 'test_debug_schema'
    file_schema = 'test_debug_schema'
    
    repo = DxfRepository(db_conn)
    
    # Check if schema exists, create if needed
    print(f"Checking schema '{layer_schema}'...")
    try:
        if not repo.schema_exists(session, layer_schema):
            print(f"  Schema doesn't exist, creating...")
            created = repo.create_schema(session, layer_schema)
            print(f"  Schema created: {created}")
        else:
            print(f"  Schema already exists")
    except Exception as e:
        print(f"  Error with schema: {e}")
    
    # Ensure file table exists
    print(f"\nEnsuring file table in '{file_schema}'...")
    try:
        result = repo.ensure_file_table(session, file_schema)
        print(f"  File table ensured: {result}")
    except Exception as e:
        print(f"  Error ensuring file table: {e}")
    
    # Load DXF
    print("\n=== Loading DXF ===")
    doc = DxfDocument(dxf_file)
    print(f"DXF loaded: {doc.is_loaded}")
    
    layers = doc.get_layers()
    print(f"Layers: {list(layers.keys())}")
    
    # Test layer table creation directly
    print("\n=== Testing Layer Table Creation ===")
    for layer_name in list(layers.keys())[:1]:  # Test first layer
        print(f"\nCreating table for layer '{layer_name}'...")
        try:
            layer_class = repo.create_layer_table(session, layer_name, layer_schema, file_schema)
            print(f"  Layer class: {layer_class}")
            if layer_class:
                print(f"  Table name: {layer_class.__tablename__}")
            else:
                print("  FAILED - layer_class is None!")
        except Exception as e:
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Close session
    session.close()
    
    # Now try the full import
    print("\n=== Full Import Test ===")
    
    config = ImportConfig(
        connection=conn_settings,
        layer_schema=layer_schema,
        file_schema=file_schema,
        export_layers_only=True,
        mapping_mode='always_overwrite'
    )
    
    import_service = ImportService()
    
    def progress_callback(percent, message):
        print(f"  [{percent}%] {message}")
    
    result = import_service.import_dxf(
        file_path=dxf_file,
        config=config,
        progress_callback=progress_callback
    )
    
    print(f"\nImport result:")
    print(f"  success: {result.success}")
    print(f"  message: {result.message}")
    print(f"  layers_imported: {result.layers_imported}")
    print(f"  entities_imported: {result.entities_imported}")
    print(f"  layer_errors: {result.layer_errors}")


if __name__ == '__main__':
    test_import()
