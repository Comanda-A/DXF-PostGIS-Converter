"""
Localization file for English language
"""

# Common strings
COMMON = {
    "yes": "Yes",
    "no": "No",
    "cancel": "Cancel",
    "ok": "OK",
    "error": "Error",
    "warning": "Warning",
    "info": "Information",
    "help": "Help",
    "confirm": "Confirm",
    "new_file": "New file",
}

# Main dialog strings
MAIN_DIALOG = {
    # Titles and names
    "export_to_db": "Export Selected",
    "export_selected_question": "Do you want to export only selected objects?",
    
    # DB connections
    "no_connections": "No PostgreSQL connections found",
    "connect_button": "Connect",
    "info_button": "Info",
    "import_button": "Import",
    "delete_button": "Delete",
    "db_empty": "Empty",
    "connection_error": "Connection error: {0}",
    "db_empty_message": "Database '{0}' is empty or doesn't support the storage structure",
    
    # DB dialogs
    "delete_file_title": "Delete File",
    "delete_file_question": "Do you really want to delete the file '{0}'?",
    "saved_credentials_error": "No saved credentials found for this connection",
    
    # File info dialog
    "file_info_title": "File Information",
    "file_info_text": "ID: {0}\nFile name: {1}\nUpload date: {2}",
    
    # DB info dialog
    "db_info_title": "Connection Information",
    "db_info_text": "Connection: {0}\nDatabase: {1}\nUsername: {2}\nPassword: {3}\nHost: {4}\nPort: {5}",
    "not_saved": "Not saved",
    
    # Import from DB
    "save_file_as": "Save file as",
    "file_path_error": "Please select a path to save the file.",
    
    # Help dialog
    "help_dialog_title": "Help - DXF-PostGIS Converter",
    
    # Errors
    "error_processing_dxf": "Error processing DXF files: {0}",
    "error_executing_task": "Error executing task: {0}",
    "error_displaying_connection": "Error displaying connection info for {0}: {1}"
}

# Logging
LOGGING = {
    "logging_enabled": "Logging enabled",
    "logging_disabled": "Logging disabled",
    "processing_connection": "Processing connection {0}",
    "item_change_error": "Error processing item change: {0}",
    "invalid_file_name": "Warning: Invalid or empty file name for item: {0}",
    "selected_file": "Selected file: {0}"
}

# Credentials dialog strings
CREDENTIALS_DIALOG = {
    "title": "Credentials for {0}",
    "username_label": "Username:",
    "password_label": "Password:",
    "failed_to_get_credentials": "Failed to get credentials for connection '{0}'",
    "remember_credentials": "Remember credentials"
}

# Attribute dialog strings
ATTRIBUTE_DIALOG = {
    "title": "Object Attributes",
    "map_column": "Map",
    "dxf_attr_column": "DXF Attribute",
    "db_attr_column": "DB Attribute"
}

# Preview components strings
PREVIEW_COMPONENTS = {
    "title": "DXF Preview",
    "instructions": "🖱️ Controls:\n• Ctrl + mouse wheel - zoom\n• Hold LMB - move\n• Double click - reset view\n• Ctrl + (+/-) - zoom\n• Ctrl + 0 - reset view\n• Esc - close",
    "reset_view": "Reset View",
    "zoom_in": "Zoom In",
    "zoom_out": "Zoom Out",
    "preview_not_found": "Preview not found at path: {0}",
    "preview_search": "Searching preview at path: {0}",
    "preview_error": "Error creating preview widget: {0}"
}

# Providers dialog strings
PROVIDERS_DIALOG = {
    "title": "Connections Editor",
    "label": "Saved Databases",
    "refresh_button": "Refresh Connections",
    "select_button": "Select"
}

# Tree widget handler strings
TREE_WIDGET_HANDLER = {
    "remove_button": "Remove",
    "file_text": "File: {0} | ({1} {2}, {3} {4})",
    "file_selection_text": "File: {0} | ({1} {2} | selected {3} {4} | {5} {6} out of {7})",
    "file": "File: ",
    "layer_text": "Layer: {0} | ({1} {2} | selected: {3} {4})",
    "layer": "Layer:",
    "selected": "selected:",
    "attributes": "Attributes",
    "geometry": "Geometry",
    "selection_confirm_title": "Confirmation",
    "selection_confirm_message": "Do you really want to select items in this file? This will clear the selection from the previous file.",
    "checking_objects": "Checking objects...",
    "cancel": "Cancel",
    "word_forms": {
        "layer": ["layer", "layers", "layers"],
        "entity": ["entity", "entities", "entities"]
    },
    "error_receiving_data" : "Error when receiving data"
}

# Export dialog strings
EXPORT_DIALOG = {
    "title": "Export to Database",
    "export_thread_start": "Starting DXF export to database",
    "export_thread_success": "Export completed successfully",
    "export_thread_complete": "Export completed successfully!",
    "progress_dialog_title": "Export",
    "progress_text": "Exporting objects to database{0}",
    "success_title": "Success",
    "error_title": "Error",
    "export_error": "Failed to complete export: {0}",
    
    # Groups and labels
    "dxf_objects_group": "DXF Objects",
    "db_connection_group": "Database Connection",
    "file_selection_group": "File Selection",
    "import_mode_group": "Import Mode",
    "mapping_group": "Layer and Field Mapping",
    
    # Labels and buttons
    "address_label": "Address:",
    "select_db_button": "Select DB",
    "port_label": "Port:",
    "db_name_label": "DB Name:",
    "schema_label": "Schema:",
    "username_label": "Username:",
    "password_label": "Password:",
    "new_file_placeholder": "Enter file name",
    "layer_select_label": "Select layer:",
    "ok_button": "Export",
    "cancel_button": "Cancel",
    
    # Import modes
    "mapping_radio": "Field Mapping",
    "overwrite_radio": "Overwrite File",
    
    # Mapping tabs
    "geom_tab": "Geometric Objects",
    "nongeom_tab": "Non-geometric Objects",
    "geom_tab_loading": "Geometric Objects (Loading...)",
    "nongeom_tab_loading": "Non-geometric Objects (Loading...)",
    "geom_tab_count": "Geometric Objects ({0})",
    "nongeom_tab_count": "Non-geometric Objects ({0})",
    "map_column": "Attributes",
    "attributes_button": "Open",
    
    # Buttons and pagination
    "prev_page": "◄",
    "next_page": "►",
    "page_label": "Page {0} of {1}",
    "back_option": "< Back",
    "more_option": "More...",
    "attr_button": "Attributes",
    
    # Messages
    "warning_title": "Warning",
    "enter_file_name": "Enter file name",
    "file_exists": "A file with this name already exists. Please choose a different name.",
    "file_check_error": "Failed to check file name: {0}",
    "loading_objects": "Loading layer objects...",
    "filtering_entities": "Filtering selected entities...",
    "loading_all_entities": "Loading all layer entities...",
    "loading_db_objects": "Loading objects from database...",
    "processing_db_objects": "Processing database objects...",
    "setting_up_mapping": "Setting up mapping tables...",
    "no_entities_found": "No entities found in layer {0}",
    "no_layers_for_selected": "No layers containing selected objects",
    "layer_load_error": "Failed to load layers: {0}",
    "table_setup_error": "Error setting up mapping table: {0}",
    
    # Tooltips
    "new_entity_tooltip": "New entity not present in database",
    "file_exists_tooltip": "File with this name already exists. Please choose a different name.",
    "file_available_tooltip": "File name available",
    "file_check_error_tooltip": "Error checking file name: {0}",
    "enter_file_name_tooltip": "Enter file name"
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

# UI strings
UI = {
    "main_dialog_title": "DXF-PostGIS Converter",
    "tab_dxf_to_sql": "DXF → SQL",
    "tab_sql_to_dxf": "SQL → DXF",
    "tab_settings": "Settings",
    "open_dxf_button": "Open DXF",
    "select_area_button": "Select Area",
    "export_to_db_button": "Export to DB",
    "file_not_selected": "No file selected :(",
    "type_shape": "Shape Type",
    "type_selection": "Selection Rule",
    "shape_rectangle": "rectangle",
    "shape_circle": "circle",
    "shape_polygon": "polygon",
    "selection_inside": "inside",
    "selection_outside": "outside",
    "selection_intersect": "overlap",
    "databases_label": "Databases",
    "enable_logs": "Enable Logs",
    "interface_language": "Interface Language"
}

DRAW = {
    "polygon_coordinates": "Polygon: {0}",
    "circle_coordinates": "Circle: Center - {0}, Radius - {1}",
    "square_coordinates": "Rectangle: Xmin - {0}, Ymin - {1}, Xmax - {2}, Ymax - {3}"
}