from qgis.core import QgsSettings, QgsProviderRegistry, QgsDataSourceUri
from qgis._core import QgsApplication, QgsAuthMethodConfig
import json
import os
from ..logger.logger import Logger

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
        
    def get_credentials(self, host, port, database, default_username=None, parent=None):
        """
        Универсальный метод для получения учетных данных подключения
        
        Аргументы:
            host (str): Хост базы данных
            port (str): Порт подключения
            database (str): Имя базы данных
            default_username (str, optional): Имя пользователя по умолчанию
            parent (QWidget, optional): Родительский виджет для диалогов
            
        Возвращает:
            tuple: (username, password)
        """
        from ..gui.credentials_dialog import CredentialsDialog
        
        # Формируем уникальный идентификатор подключения
        conn_display_name = f"{host}:{port}/{database}"
        
        # Сначала ищем в сохраненных подключениях
        conn = self.get_connection(conn_display_name)
        if conn:
            Logger.log_message(f"Используем сохраненные учетные данные для {conn_display_name}")
            return conn['username'], conn['password']
            
        # Пробуем найти соответствующее подключение в QGIS
        username, password = None, None
        for name, metadata in QgsProviderRegistry.instance().providerMetadata('postgres').connections().items():
            try:
                uri_check = QgsDataSourceUri(metadata.uri())
                if (uri_check.host() == host and 
                    uri_check.port() == port and 
                    uri_check.database() == database):
                    
                    # Пробуем извлечь учетные данные из URI
                    uri = uri_check
                    
                    # Проверяем прямые учетные данные
                    if uri.username() and uri.password():
                        username = uri.username()
                        password = uri.password()
                        Logger.log_message(f"Учетные данные получены из URI для '{conn_display_name}'")
                        break
                        
                    # Проверяем AuthConfig
                    elif uri.authConfigId():
                        auth_mgr = QgsApplication.authManager()
                        if auth_mgr:
                            auth_cfg = QgsAuthMethodConfig()
                            if auth_mgr.loadAuthenticationConfig(uri.authConfigId(), auth_cfg, True):
                                username = auth_cfg.config('username', '')
                                password = auth_cfg.config('password', '')
                                if username and password:
                                    Logger.log_message(f"Учетные данные получены из AuthConfig для '{conn_display_name}'")
                                    break
                    
                    # Проверяем строку подключения
                    elif uri.connectionInfo():
                        conn_info = uri.connectionInfo()
                        params = conn_info.split(' ')
                        for param in params:
                            if param.startswith('user='):
                                username = param.split('=')[1].strip("'")
                            elif param.startswith('password='):
                                password = param.split('=')[1].strip("'")
                        if username and password:
                            Logger.log_message(f"Учетные данные получены из connectionInfo для '{conn_display_name}'")
                            break
                    
                    # Проверяем файл сервиса PostgreSQL
                    elif uri.service():
                        pgservicefile = os.path.expanduser("~/.pg_service.conf")
                        if os.path.exists(pgservicefile):
                            try:
                                with open(pgservicefile, 'r') as f:
                                    current_service = None
                                    for line in f:
                                        line = line.strip()
                                        if line.startswith('[') and line.endswith(']'):
                                            current_service = line[1:-1]
                                        elif current_service == uri.service() and '=' in line:
                                            key, value = line.split('=', 1)
                                            key = key.strip()
                                            value = value.strip()
                                            if key == 'password':
                                                password = value
                                            elif key == 'user':
                                                username = value
                                if username and password:
                                    Logger.log_message(f"Учетные данные получены из pg_service.conf для '{conn_display_name}'")
                                    break
                            except Exception as e:
                                Logger.log_error(f"Ошибка при чтении pg_service.conf: {str(e)}")
            except Exception as e:
                Logger.log_error(f"Ошибка при проверке соединения: {str(e)}")
                continue
        
        # Если не удалось получить учетные данные, запрашиваем у пользователя
        if not (username or password):
            Logger.log_message(f"Запрашиваем ввод учетных данных для {conn_display_name}")
            username, password = CredentialsDialog.get_credentials_for_connection(
                conn_display_name, parent, default_username or '')
                
            if not (username and password):
                Logger.log_message(f"Пользователь отменил ввод учетных данных для {conn_display_name}")
                return None, None
        
        # Сохраняем учетные данные для будущего использования
        self.save_connection(conn_display_name, username, password)
        Logger.log_message(f"Учетные данные для '{conn_display_name}' сохранены")
        
        return username, password
