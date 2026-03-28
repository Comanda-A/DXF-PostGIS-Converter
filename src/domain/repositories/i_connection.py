
from abc import ABC, abstractmethod
from ...domain.value_objects import ConnectionConfig, Result, Unit

class IConnection(ABC):
    """Интерфейс для подключения к базе данных"""
    
    @property
    @abstractmethod
    def db_type(self) -> str:
        """Тип базы данных"""
        pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Проверяет, установлено ли соединение с базой данных"""
        pass
    
    @abstractmethod
    def connect(self, config: ConnectionConfig) -> Result[Unit]:
        """Устанавливает соединение с базой данных"""
        pass
    
    @abstractmethod
    def close(self) -> Result[Unit]:
        """Закрывает соединение с базой данных"""
        pass
    
    @abstractmethod
    def commit(self) -> Result[Unit]:
        pass
    
    @abstractmethod
    def rollback(self) -> Result[Unit]:
        pass
    
    @abstractmethod
    def get_schemas(self) -> Result[list[str]]:
        """Список всех схем в базе данных"""
        pass

    @abstractmethod
    def schema_exists(self, schema_name: str) -> Result[bool]:
        """Проверяет существование схемы"""
        pass

    @abstractmethod
    def create_schema(self, schema_name: str) -> Result[Unit]:
        """Создает новую схему"""
        pass

    @abstractmethod
    def drop_schema(self, schema_name: str, cascade: bool = False) -> Result[Unit]:
        """Удаляет схему"""
        pass
    
    @abstractmethod
    def get_tables(self, schema_name: str) -> Result[list[str]]:
        """Список таблиц в схеме"""
        pass
