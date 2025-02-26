from qgis.core import QgsSettings
import json
import os

class ConnectionsManager:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConnectionsManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.connections = {}
        self.load_connections()
    
    def load_connections(self):
        """Загружает сохраненные подключения из настроек QGIS"""
        settings = QgsSettings()
        connections_json = settings.value("DXFPostGIS/connections", "{}")
        try:
            self.connections = json.loads(connections_json)
        except json.JSONDecodeError:
            self.connections = {}
    
    def save_connections(self):
        """Сохраняет все подключения в настройки QGIS"""
        settings = QgsSettings()
        connections_json = json.dumps(self.connections)
        settings.setValue("DXFPostGIS/connections", connections_json)
    
    def get_connection(self, conn_name):
        """Возвращает сохраненные учетные данные для подключения"""
        return self.connections.get(conn_name)
    
    def save_connection(self, conn_name, username, password):
        """Сохраняет учетные данные для подключения"""
        self.connections[conn_name] = {
            'username': username,
            'password': password
        }
        self.save_connections()
    
    def delete_connection(self, conn_name):
        """Удаляет сохраненное подключение"""
        if conn_name in self.connections:
            del self.connections[conn_name]
            self.save_connections()
            return True
        return False
    
    def get_all_connections(self):
        """Возвращает список всех сохраненных имен подключений"""
        return list(self.connections.keys())
