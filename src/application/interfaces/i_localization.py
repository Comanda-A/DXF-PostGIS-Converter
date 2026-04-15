
from abc import ABC, abstractmethod
from typing import Dict, Optional

class ILocalization(ABC):

    @abstractmethod
    def tr(self, category: str, key: str, *args) -> Optional[str]:
        """Возвращает перевод по категории и ключу. Заполняет пропуски args"""
        pass

    @property
    @abstractmethod
    def language_code(self) -> str:
        """Код текущего языка"""
        pass
    
    @property
    @abstractmethod
    def language_name(self) -> str:
        """Название текущего языка"""
        pass

    @property
    @abstractmethod
    def available_languages(self) -> Dict[str, str]:
        """Возвращает словарь доступных языков в формате {код: название}"""
        pass

    @abstractmethod
    def set_language_by_name(self, name: str) -> bool:
        """Устанавливает язык по названию."""
        pass

    @abstractmethod
    def set_language_by_code(self, code: str) -> bool:
        """Устанавливает язык по коду."""
        pass

    @abstractmethod
    def get_all_translations(self, category: str) -> Dict[str, str]:
        """Возвращает словарь всех переводов для указанной категории {ключ: перевод}"""
        pass
    
    