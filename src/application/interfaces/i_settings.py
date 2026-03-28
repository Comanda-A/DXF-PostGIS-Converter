
from abc import ABC, abstractmethod
from typing import Any

class ISettings(ABC):

    @abstractmethod
    def get_value(self, key: str, default=None, value_type=None) -> Any:
        """Получить значение из настроек"""
        pass
    
    @abstractmethod
    def set_value(self, key: str, value) -> None:
        """Установить значение в настройки"""
        pass
    
    @abstractmethod
    def remove(self, key: str) -> None:
        """Удалить ключ из настроек"""
        pass
