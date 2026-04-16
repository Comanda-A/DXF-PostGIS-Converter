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
    "EXPORT_DIALOG": """
<h2>Export Dialog Interface Guide</h2>

<h3>Left Column</h3>
<h4>DXF Objects Section</h4>
<ul>
    <li><b>Tree Widget:</b> Shows the hierarchy of DXF objects selected for export</li>
</ul>

<h4>Database Connection Section</h4>
<ul>
    <li><b>DB Selection Button:</b> Opens a dialog to select PostgreSQL connection</li>
    <li><b>Address:</b> Shows current database server address</li>
    <li><b>Port:</b> Database server port (default: 5432)</li>
    <li><b>DB Name:</b> Selected database name</li>
    <li><b>Schema:</b> Selected database schema</li>
    <li><b>Username:</b> Database user login</li>
    <li><b>Password:</b> Database user password</li>
</ul>

<h3>Right Column</h3>
<h4>File Selection Section</h4>
<ul>
    <li><b>Files Dropdown:</b> Choose between creating a new file or selecting an existing one</li>
    <li><b>New File Name:</b> Input field for the new file name (active only for new files)</li>
</ul>

<h4>Import Mode Section</h4>
<p>Available when selecting an existing file:</p>
<ul>
    <li><b>Field Mapping:</b> Allows manual mapping of DXF and database fields</li>
    <li><b>Overwrite File:</b> Completely replaces existing file content</li>
</ul>

<h4>Layer and Field Mapping Section</h4>
<p>Displayed when selecting "Field Mapping" mode:</p>
<ul>
    <li><b>Layer Selection:</b> Choose layer for mapping</li>
    <li><b>Geometric Objects Tab:</b> Mapping for objects containing geometry</li>
    <li><b>Non-geometric Objects Tab:</b> Mapping for objects without geometry</li>
</ul>

<h4>Mapping Tables</h4>
<ul>
    <li><b>DXF Entity Column:</b> Shows DXF object identifiers</li>
    <li><b>DB Entity Column:</b> Dropdown list for selecting corresponding database object</li>
    <li><b>Actions Column:</b> "Show Attributes" button for viewing and mapping detailed attributes</li>
</ul>

<h3>Additional Features</h3>
<ul>
    <li>Yellow highlighting indicates new entities not present in the database</li>
    <li>Dialog automatically saves and loads the last used database connection</li>
    <li>All mappings are saved during the session until export is completed</li>
</ul>
""",
"MAIN_DIALOG": """
<h2>Main Interface Guide</h2>

<h3>DXF → SQL Tab</h3>
<h4>Top Control Panel</h4>
<ul>
    <li><b>"Open DXF" Button:</b> Opens a file dialog to select DXF files</li>
    <li><b>"Select area" Button:</b> Activates the area selection tool on the map. The result is the selection in the objects tree that fall within the selected area</li>
    <li><b>"Export to DB" Button:</b> Opens the database export dialog</li>
    <li><b>File Indicator:</b> Shows the name of the currently open file</li>
</ul>

<h4>Selection Parameters Panel</h4>
<ul>
    <li><b>Coordinates Text Field:</b> Displays coordinates of the selected area</li>
    <li><b>Shape Type:</b> Selection area type (rectangle/circle/polygon)</li>
    <li><b>Selection Rule:</b> Determines how objects are selected (inside/outside/intersection)</li>
</ul>

<h4>DXF Objects Tree</h4>
<ul>
    <li>Displays hierarchy of DXF file layers and objects</li>
    <li>Allows selecting objects for export</li>
    <li>Shows number of objects in each layer</li>
</ul>

<h3>SQL → DXF Tab</h3>
<h4>Database Structure</h4>
<ul>
    <li>Tree view of available database connections</li>
    <li>For each connection shows:
        <ul>
            <li>List of saved DXF files</li>
            <li>File management buttons (preview/import/delete/info)</li>
        </ul>
    </li>
</ul>

<h3>Additional Features</h3>
<ul>
    <li>DXF file preview before import</li>
    <li>Automatic connection settings saving</li>
    <li>Multiple object selection support</li>
    <li>Interactive area selection on map</li>
</ul>

<h3>Hotkeys</h3>
<ul>
    <li><b>Ctrl+Tab:</b> Switch between tabs</li>
</ul>
"""
}
