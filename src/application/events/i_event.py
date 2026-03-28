
from typing import TypeVar, Generic, Callable, Any
from abc import ABC, abstractmethod

T = TypeVar('T', covariant=True)

class IEvent(ABC, Generic[T]):
    
    @abstractmethod
    def connect(self, slot: Callable[[T], None]) -> None:
        """Подключить слот к сигналу"""
        pass
    
    @abstractmethod
    def disconnect(self, slot: Callable[[T], None]) -> bool:
        """Отключить слот от сигнала"""
        pass
    
    @abstractmethod
    def emit(self, data: T) -> None:
        """Испустить сигнал с данными"""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Отключить все слоты"""
        pass
