
from typing import Type
from ...domain.value_objects import ConnectionConfig, Result, Unit
from ...domain.repositories import IConnection, IConnectionFactory

class ConnectionFactory(IConnectionFactory):
    """Фабрика для создания соединений с базой данных"""
    
    def __init__(self, connection_classes: list[Type[IConnection]]):
        self._available_connections: dict[str, Type[IConnection]] = {}
        for conn_class in connection_classes:
            self.register_connection(conn_class)

    def register_connection(self, connection_class: Type[IConnection]) -> Result[Unit]:
        try:
            connection = connection_class()
            self._available_connections[connection.db_type] = connection_class
            return Result.success(Unit())
        except Exception as e:
            return Result.fail(f"Failed register connection: {e}")
    
    def get_supported_databases(self) -> list[str]:
        return list(self._available_connections.keys())
    
    def get_connection(self, db_type: str) -> Result[IConnection]:

        connection_class = self._available_connections.get(db_type)
        
        if connection_class is None:
            return Result.fail(f"Unsupported database type: {db_type}")
        
        try:
            connection = connection_class()
            return Result.success(connection)
        except Exception as e:
            return Result.fail(f"Error creating connection for '{db_type}': {str(e)}")
