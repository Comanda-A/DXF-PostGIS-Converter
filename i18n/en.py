"""
Localization file for English language
"""

CONFIG = {
    "code": "en",
    "name": "English"
}

# Main dialog strings
MAIN_DIALOG = {
    "dialog_title": "DXF-PostGIS Converter",
    "help_dialog_title": "Help",

    "tab_dxf_to_db": "Import",
    "tab_db_to_dxf": "Export",
    "tab_settings": "Settings",

    "open_dxf_button": "Open DXF",
    "import_dxf_button": "Import to DB",
    "save_dxf_button": "Save to file..",
    "connection_editor_button": "Connection Editor",
    "current_connection_label": "Current connection:",
    "schema_label": "File schema:",
    "refresh_db_button": "Refresh files",
    "export_db_button": "Export",
    "apply_filter_button": "Apply",
    "clear_filter_button": "Clear",
    "select_area_button": "Select area on map",

    "filter_group": "Selection Filter",
    "selection_group": "Selection Area",

    "file_label": "File:",
    "search_label": "Search:",
    "figure_label": "Figure type:",
    "rule_label": "Selection rule:",
    "mode_label": "Selection mode:",
    "coord_label": "Area coordinates:",
    "db_structure_label": "Database structure:",
    "language_label": "Interface language:",
    "dxf_tree_label": "DXF file structure:",

    "layer_search_edit": "Layer name...",
    "coord_edit": "Select area on map...",

    "shape_rectangle": "Rectangle",
    "shape_circle": "Circle",
    "shape_polygon": "Polygon",
    "selection_inside": "Inside",
    "selection_outside": "Outside",
    "selection_intersect": "Intersect",
    "mode_join": "Union",
    "mode_replace": "Replace",
    "mode_subtract": "Subtract",

    "logging_check": "Enable operation logging",
    "db_files_empty": "No files found",
    "select_files_to_export": "Select at least one file to export.",
    "select_connection_first": "Select a database connection first.",
    "select_schema_first": "Select a schema with DXF files first.",
    "select_file_first": "Select a DXF file first.",
    "choose_export_folder": "Select export folder",
    "save_as": "Save As",
    "export_success_qgis": "Export completed. Files loaded into QGIS: {}",
    "export_success_folder": "Export completed. Files saved to: {}",
    "export_in_progress": "Export in progress...",
    "cancel": "Cancel"
}

IMPORT_DIALOG = {
    "dialog_title": "DXF to PostGIS Import",
    "help_dialog_title": "Import Help",
    
    # Группы
    "dxf_files_group": "DXF Files",
    "database_connection_group": "Database Connection",
    "import_settings_group": "Import Settings",
    "layers_schema_group": "Layer Schema Parameters",
    "files_schema_group": "File Schema Parameters",
    
    # Кнопки подключения к БД
    "select_database_button": "Select Database",
    "connect_button": "Connect",
    
    # Лейблы подключения к БД
    "address_label": "Address:",
    "port_label": "Port:",
    "database_name_label": "Database Name:",
    "username_label": "Username:",
    "password_label": "Password:",
    
    # Настройки импорта
    "filename_label": "File Name:",
    "layer_mapping_label": "Layer Mapping Mode:",
    "layer_mapping_hint_label": "All existing objects will be replaced with new ones",
    
    # ComboBox режима маппирования
    "import_mode_overwrite": "Always Overwrite",
    "import_mode_append": "Append to Existing",
    "import_mode_skip": "Skip Existing Layers",
    
    # Параметры схемы слоев
    "layers_schema_label": "Schema for Layers:",
    "create_layers_schema_button": "Create New Schema",
    
    # Параметры схемы файлов
    "import_only_layers_check": "Import Only Layers",
    "import_only_layers_hint_label": "Data loss possible when exporting",
    "files_schema_label": "Schema for Files:",
    "create_files_schema_button": "Create New Schema",
    
    # Кнопки внизу
    "cancel_button": "Cancel",
    "import_button": "Import"
}

TREE_WIDGET_HANDLER = {

    "file_text": "{} | selected layers: {}/{} | selected entities: {}/{}",
    "layer_text": "{} | selected entities: {}/{}",
    "preview_button": "Preview",
    "remove_button": "Close"
}

DB_TREE_HANDLER = {
    "preview_button": "Preview",
    "info_button": "Info",
    "delete_button": "Delete"
}

CONNECTION_EDITOR_DIALOG = {
    "dialog_title": "Connection Editor",
    "update_button": "Update",
    "add_button": "Add Connection",
    "select_button": "Select",
    "error_title": "Error",
    "info_title": "Information",
    "load_connections_error": "Failed to load connections list",
    "schemas_load_failed": "Failed to load schemas",
    "schemas_load_error": "Failed to load database schemas",
    "no_schemas_available": "No schemas available",
    "tables_load_failed": "Failed to load tables",
    "edit_action": "Edit",
    "delete_action": "Delete",
    "delete_confirmation_title": "Confirm Deletion",
    "delete_confirmation_message": "Are you sure you want to delete connection '{}'?",
    "delete_error": "Failed to delete connection '{}'",
    "select_connection_prompt": "Please select a connection."
}

CONNECTION_DIALOG = {
    "dialog_title": "New Connection",
    "connection_group": "Connection Information",
    "dbms_label": "DBMS",
    "name_label": "Connection Name",
    "address_label": "Host",
    "port_label": "Port",
    "database_label": "Database",
    "username_label": "Username",
    "password_label": "Password",
    "check_button": "Test Connection",
    "ok_button": "OK",
    "cancel_button": "Cancel",

    "warning_title": "Warning",
    "error_title": "Error",
    "success_title": "Success",
    "confirmation_title": "Confirmation",
    
    "name_required": "Connection name is required",
    "address_required": "Server address is required",
    "port_required": "Port is required",
    "database_required": "Database name is required",
    "username_required": "Username is required",
    
    "connection_successful": "Connection successfully established",
    "connection_failed": "Failed to establish connection. {}",
    "connection_check_error": "Error checking connection. {}",
    
    "connection_exists": "Connection with name '{}' already exists. Overwrite?",
    "save_error": "Error saving connection. {}"
}

# Help content for dialogs
HELP_CONTENT = {
    "IMPORT_DIALOG": """
<h2>DXF to PostGIS Import Dialog Guide</h2>

<h3>What this dialog does</h3>
<p>This dialog imports selected DXF files into PostgreSQL/PostGIS. During import, the DB file record is created automatically together with related layer/entity storage.</p>

<h3>Database structure created by import</h3>
<ul>
    <li><b>files (in files schema):</b> DXF document registry: <code>id</code>, <code>filename</code>, <code>upload_date</code>, <code>update_date</code>.</li>
    <li><b>layers (in files schema):</b> document layers: <code>id</code>, <code>document_id</code>, <code>name</code>, <code>schema_name</code>, <code>table_name</code>.</li>
    <li><b>content (in files schema):</b> file binary payload: <code>id</code>, <code>document_id</code>, <code>content (BYTEA)</code>.</li>
    <li><b>Layer table (in layer schema):</b> for each layer, a dedicated entity table is created/used with <code>id</code>, <code>entity_type</code>, <code>name</code>, <code>geometry</code>, <code>attributes (JSONB)</code>, <code>geometries (JSONB)</code>, <code>extra_data (JSONB)</code>.</li>
</ul>

<h3>Entities and relationships (as implemented)</h3>
<table border="1" cellpadding="4" cellspacing="0">
    <tr><th>Code entity</th><th>Stored in</th><th>Linking rule</th></tr>
    <tr><td>DXFDocument</td><td>files</td><td>By <code>id</code>; file name is unique (<code>filename UNIQUE</code>)</td></tr>
    <tr><td>DXFLayer</td><td>layers</td><td><code>layers.document_id -> files.id</code> (logical UUID link)</td></tr>
    <tr><td>DXFContent</td><td>content</td><td><code>content.document_id -> files.id</code> (logical UUID link)</td></tr>
    <tr><td>DXFEntity</td><td>Dedicated layer table</td><td>Table name comes from <code>layers.schema_name</code> + <code>layers.table_name</code></td></tr>
</table>

<p><b>Note:</b> in the current implementation, these links are maintained at the application level via UUID fields and repository parameters.</p>

<h3>Main controls</h3>
<ul>
    <li><b>DXF files tree:</b> select which file you are configuring for import.</li>
    <li><b>Database connection:</b> select saved connection and confirm active session.</li>
    <li><b>Import mode:</b> overwrite layers, update+append, or append-only.</li>
    <li><b>Layer/files schemas:</b> choose where to create/update structures.</li>
    <li><b>Import only layers:</b> faster mode without full file structure (may limit completeness).</li>
    <li><b>Transliteration:</b> normalizes layer names for table naming compatibility.</li>
</ul>
""",
"MAIN_DIALOG": """
<h2>Main Interface Guide</h2>

<h3>Import Tab (DXF -> DB)</h3>
<h4>Top controls</h4>
<ul>
    <li><b>Open DXF:</b> adds one or more DXF files to the working tree.</li>
    <li><b>Select area on map:</b> selects entities by geometry (rectangle/circle/polygon) and selection rule.</li>
    <li><b>Selection filter:</b> file selection, layer search, check/uncheck layers, apply filter to entities.</li>
    <li><b>Save to file:</b> creates a new DXF from selected entities. Recommended before import when you need maximum attribute preservation for a specific subset.</li>
    <li><b>Import to DB:</b> opens the import dialog and writes data into PostGIS.</li>
</ul>

<h3>Export Tab (DB -> DXF)</h3>
<ul>
    <li><b>Connection editor:</b> create/edit/select PostgreSQL/PostGIS connections.</li>
    <li><b>Connection and schema selection:</b> choose where DXF data is read from.</li>
    <li><b>Refresh files:</b> reload available files from selected schema.</li>
    <li><b>Export:</b> extracts a stored DXF file from the database and writes it to disk (or opens it in QGIS flow).</li>
</ul>

<h3>Actual storage model (short)</h3>
<table border="1" cellpadding="4" cellspacing="0">
    <tr><th>Object</th><th>Actual storage</th><th>How it links</th></tr>
    <tr><td>DXF file</td><td><code>files</code> table</td><td><code>id</code>, <code>filename</code></td></tr>
    <tr><td>DXF layer</td><td><code>layers</code> table</td><td><code>document_id</code> points to document</td></tr>
    <tr><td>File content</td><td><code>content</code> table (BYTEA)</td><td><code>document_id</code> points to document</td></tr>
    <tr><td>Layer entities</td><td>Dedicated layer table in <code>layer schema</code></td><td>Table name is stored in <code>layers.table_name</code></td></tr>
</table>

<h3>Settings Tab</h3>
<ul>
    <li><b>Interface language:</b> switch localization at runtime.</li>
    <li><b>Logging:</b> enable/disable operation logging for diagnostics.</li>
</ul>

<h3>Hotkey</h3>
<ul>
    <li><b>Ctrl+Tab:</b> switch between tabs.</li>
</ul>
"""
}
