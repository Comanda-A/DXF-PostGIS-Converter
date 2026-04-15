
from typing import Type
from abc import ABC, abstractmethod
from ...domain.value_objects import Result, Unit
from ...domain.repositories import IConnection

class IConnectionFactory(ABC):
    """Фабрика для создания соединений"""
    
    @abstractmethod
    def register_connection(self, connection_class: Type[IConnection]) -> Result[Unit]:
        pass
    
    @abstractmethod
    def get_supported_databases(self) -> list[str]:
        pass

    @abstractmethod
    def get_connection(cls, db_type: str) -> Result[IConnection]:
        pass
