from __future__ import annotations

import os
import json

from ...domain.repositories import IConnectionFactory
from ...application.dtos import ConnectionConfigDTO
from ...application.results import AppResult, Unit
from ...application.interfaces import ILogger, IQgisConnectionProvider

class ConnectionConfigService:
    
    # Имя файла для хранения подключений
    CONNECTIONS_FILE = "connections.json"
    
    def __init__(
        self,
        plugin_dir: str,
        connection_factory: IConnectionFactory,
        logger: ILogger,
        qgis_connection_provider: IQgisConnectionProvider | None = None
    ):
        self._plugin_dir = plugin_dir
        self._connections_file = os.path.join(self._plugin_dir, self.CONNECTIONS_FILE)
        self._connection_factory = connection_factory
        self._logger = logger
        self._qgis_provider = qgis_connection_provider

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
        """Сохранить конфигурацию подключения."""
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
        """
        Возвращает все подключения - локальные и из QGIS.
        """
        result = self._load_connections()
        
        if result.is_fail:
            return []
        
        connections_dict = result.value
        connections = []
        local_connection_names = set()
        
        # Загружаем локальные подключения
        for conn_name, conn_data in connections_dict.items():
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
            local_connection_names.add(conn_name)
        
        # Загружаем подключения из QGIS (только если они не в локальном файле)
        if self._qgis_provider:
            try:
                qgis_connections = self._qgis_provider.get_qgis_connections()
                for qgis_config in qgis_connections:
                    # Добавляем только если этого подключения нет в локальном файле
                    if qgis_config.name not in local_connection_names:
                        modified_config = ConnectionConfigDTO(
                            db_type=qgis_config.db_type,
                            name=qgis_config.name,
                            host=qgis_config.host,
                            port=qgis_config.port,
                            database=qgis_config.database,
                            username=qgis_config.username,
                            password=""  # QGIS подключения без пароля по умолчанию
                        )
                        connections.append(modified_config)
            except Exception as e:
                self._logger.warning(f"Failed to load QGIS connections: {str(e)}")
        
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
    
    def import_qgis_connections(self) -> AppResult[list[ConnectionConfigDTO]]:
        """
        Импортировать подключения из QGIS.
        
        Returns:
            AppResult[list[ConnectionConfigDTO]]: Список импортированных подключений.
        """
        if not self._qgis_provider:
            error_msg = "QGIS connection provider is not available"
            self._logger.error(error_msg)
            return AppResult.fail(error_msg)
        
        try:
            qgis_connections = self._qgis_provider.get_qgis_connections()
            self._logger.message(f"Found {len(qgis_connections)} QGIS connections")
            return AppResult.success(qgis_connections)
        except Exception as e:
            error_msg = f"Error importing QGIS connections: {str(e)}"
            self._logger.error(error_msg)
            return AppResult.fail(error_msg)
    
    def save_qgis_connection_with_password(
        self, 
        qgis_connection: ConnectionConfigDTO, 
        password: str
    ) -> AppResult[Unit]:
        """
        Сохранить подключение из QGIS с указанным паролем.
        
        Args:
            qgis_connection: Подключение из QGIS.
            password: Пароль для подключения.
            
        Returns:
            AppResult[Unit]: Результат сохранения.
        """
        if not qgis_connection.name:
            return AppResult.fail("Connection name is required")
        
        # Создаем новое подключение с указанным паролем
        updated_connection = ConnectionConfigDTO(
            db_type=qgis_connection.db_type,
            name=qgis_connection.name,
            host=qgis_connection.host,
            port=qgis_connection.port,
            database=qgis_connection.database,
            username=qgis_connection.username,
            password=password
        )
        
        # Сохраняем
        return self.save_config(updated_connection)
    
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