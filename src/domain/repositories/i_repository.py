
from abc import ABC, abstractmethod
from typing import Optional, TypeVar, Generic
from uuid import UUID
from ...domain.value_objects import Result, Unit

T = TypeVar('T')

class IRepository(ABC, Generic[T]):
    """Базовый интерфейс репозитория"""
    
    @abstractmethod
    def create(self, entity: T) -> Result[T]:
        pass
    
    @abstractmethod
    def update(self, entity: T) -> Result[T]:
        pass
    
    @abstractmethod
    def remove(self, id: UUID) -> Result[Unit]:
        pass
    
    @abstractmethod
    def get_by_id(self, id: UUID) -> Result[Optional[T]]:
        pass
