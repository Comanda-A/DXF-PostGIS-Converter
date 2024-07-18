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
    global db_connections
    db_connections[db_name] = {
        'user': user,
        'password': password,
        'host': host,
        'port': port
    }
    save_connections_to_file()
    call_event_db_connection_changed()
    Logger.log_message(f"Connection for database '{db_name}' saved successfully.")

def get_connection(db_name):
    global db_connections
    return db_connections.get(db_name, None)

def get_all_db_names():
    global db_connections
    return list(db_connections.keys())

load_connections()