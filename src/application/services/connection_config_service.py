from __future__ import annotations

import os
import json

from ...domain.repositories import IConnectionFactory
from ...application.dtos import ConnectionConfigDTO
from ...application.results import AppResult, Unit
from ...application.interfaces import ILogger

class ConnectionConfigService:
    
    # Имя файла для хранения подключений
    CONNECTIONS_FILE = "connections.json"
    
    def __init__(
        self,
        plugin_dir: str,
        connection_factory: IConnectionFactory,
        logger: ILogger
    ):
        self._plugin_dir = plugin_dir
        self._connections_file = os.path.join(self._plugin_dir, self.CONNECTIONS_FILE)
        self._connection_factory = connection_factory
        self._logger = logger

        try:
            if not os.path.exists(self._plugin_dir):
                os.makedirs(self._plugin_dir)
                self._logger.message(f"Created plugin directory: {self._plugin_dir}")
            
            if not os.path.exists(self._connections_file):
                self._save_connections([])
                self._logger.message(f"Created connections file: {self._connections_file}")
        except Exception as e:
            self._logger.error(f"Error initializing ConnectionManager: {str(e)}")
            raise

    def get_supported_databases(self) -> list[str]:
        databases = self._connection_factory.get_supported_databases()
        return databases

    def save_config(self, config: ConnectionConfigDTO) -> AppResult[Unit]:
        # Получаем существующие подключения
        result = self._load_connections()
        
        if result.is_fail:
            return result
        
        connections = result.value
        
        # Добавляем или обновляем подключение
        connections[config.name] = {
            'db_type': config.db_type,
            'host': config.host,
            'port': config.port,
            'database': config.database,
            'username': config.username,
            'password': config.password,
            'name': config.name
        }
        
        # Сохраняем в файл
        save_result = self._save_connections(connections)
        return save_result
    
    def get_all_configs(self) -> list[ConnectionConfigDTO]:
        result = self._load_connections()
        
        if result.is_fail:
            return []
        
        connections_dict = result.value
        connections = []
        
        for conn_name, conn_data in connections_dict.items():
            # Создаем DTO объект
            connection = ConnectionConfigDTO(
                db_type=conn_data.get('db_type'),
                name=conn_data.get('name'),
                host=conn_data.get('host'),
                port=conn_data.get('port'),
                database=conn_data.get('database'),
                username=conn_data.get('username'),
                password=conn_data.get('password')
            )
            connections.append(connection)
        
        return connections
    
    def get_config_by_name(self, name: str) -> ConnectionConfigDTO | None:
        """Возвращает подключение по имени."""
        result = self._load_connections()
        
        if result.is_fail:
            return None
        
        connections = result.value

        if name in connections:
            conn_data = connections[name]
            return ConnectionConfigDTO(
                db_type=conn_data.get('db_type'),
                name=conn_data.get('name'),
                host=conn_data.get('host'),
                port=conn_data.get('port'),
                database=conn_data.get('database'),
                username=conn_data.get('username'),
                password=conn_data.get('password')
            )
        else:
            return None
    
    def delete_config(self, name: str) -> AppResult[Unit]:
        """Удаляет подключение по имени."""
        result = self._load_connections()
        
        if result.is_fail:
            return result
        
        connections = result.value
        
        if name in connections:
            del connections[name]
            save_result = self._save_connections(connections)
            return save_result
        
        self._logger.warning(f"Attempted to delete non-existent connection: '{name}'")
        return AppResult.success(Unit())
    
    def _load_connections(self) -> AppResult[dict]:
        try:
            if not os.path.exists(self._connections_file):
                error_msg = f"Connections file not found: '{self._connections_file}'"
                self._logger.error(error_msg)
                return AppResult.fail(error_msg)
            with open(self._connections_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return AppResult.success(dict(data))
        except json.JSONDecodeError as e:
            error_msg = f"JSON decode error in connections file. {str(e)}"
            self._logger.error(error_msg)
            return AppResult.fail(error_msg)
        except IOError as e:
            error_msg = f"IO error reading connections file. {str(e)}"
            self._logger.error(error_msg)
            return AppResult.fail(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error in _load_connections. {str(e)}"
            self._logger.error(error_msg)
            return AppResult.fail(error_msg)
    
    def _save_connections(self, connections: dict) -> AppResult[Unit]:
        try:
            with open(self._connections_file, 'w', encoding='utf-8') as f:
                json.dump(connections, f, indent=2, ensure_ascii=False)
                return AppResult.success(Unit())
        except IOError as e:
            error_msg = f"IO error saving connections file. {str(e)}"
            self._logger.error(error_msg)
            return AppResult.fail(error_msg)
        except TypeError as e:
            error_msg = f"JSON serialization error. {str(e)}"
            self._logger.error(error_msg)
            return AppResult.fail(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error in _save_connections. {str(e)}"
            self._logger.error(error_msg)
            return AppResult.fail(error_msg)