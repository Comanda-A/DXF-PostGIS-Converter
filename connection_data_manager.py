import os
import json
from .logger import Logger


DIRECTORY = os.path.expanduser("~/Documents/DXF-PostGIS-Converter")
FILENAME = "db_connections.json"
FILEPATH = os.path.join(DIRECTORY, FILENAME)


os.makedirs(DIRECTORY, exist_ok=True)

db_connections = {}
event_db_connection_changed = []


def call_event_db_connection_changed():
    event_db_connection_changed
    for action in event_db_connection_changed:
            action()
def load_connections():
    global db_connections
    if os.path.exists(FILEPATH):
        with open(FILEPATH, 'r') as file:
            db_connections = json.load(file)
    else:
        db_connections = {}
    call_event_db_connection_changed()


def save_connections_to_file():
    with open(FILEPATH, 'w') as file:
        json.dump(db_connections, file, indent=4)


def save_connection(db_name, user, password, host, port):
    db_connections[db_name] = {
        'user': user,
        'password': password,
        'host': host,
        'port': port,
        'table_name': None
    }
    save_connections_to_file()
    call_event_db_connection_changed()
    Logger.log_message(f"Connection for database '{db_name}' saved successfully.")

def get_connection(db_name):
    return db_connections.get(db_name, None)

def get_all_db_names():
    return list(db_connections.keys())

def delete_connection(db_name):
    global db_connections
    if db_name in db_connections:
        del db_connections[db_name]
        save_connections_to_file()
        call_event_db_connection_changed()
def get_all_table_name_in_current_db(db_name):
    """Get all table names for the current database."""
    connection = db_connections.get(db_name, {})
    return connection.get('table_names', [])

def get_table_name_in_current_db(db_name, table_name):
    """Get a specific table name from the current database."""
    table_names = get_all_table_name_in_current_db(db_name)
    if table_name in table_names:
        return table_name
    return None

def delete_table_name_in_current_db(db_name, table_name):
    """Delete a table name from the current database."""
    if db_name in db_connections:
        table_names = db_connections[db_name].get('table_names', [])
        if table_name in table_names:
            table_names.remove(table_name)
            # Update the database connection with the new table list
            db_connections[db_name]['table_names'] = table_names
            save_connections_to_file()
            call_event_db_connection_changed()
            
def save_table_name_in_current_db(db_name, table_name):
    """Save or update a table name for the current database."""
    if db_name in db_connections:
        table_names = db_connections[db_name].get('table_names', [])
        if table_name not in table_names:
            table_names.append(table_name)
        db_connections[db_name]['table_names'] = table_names
        save_connections_to_file()
        call_event_db_connection_changed()
load_connections()