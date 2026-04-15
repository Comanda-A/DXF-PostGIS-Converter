
from dataclasses import dataclass
from typing import Generic, TypeVar, Optional

T = TypeVar('T')  # Тип успешного значения


@dataclass(frozen=True)
class Result(Generic[T]):
    """Результат операции"""
    
    _success: bool
    _value: Optional[T] = None
    _error: Optional[str] = None
    
    def __post_init__(self):
        """Валидация при создании"""
        if self._success and self._value is None:
            raise ValueError("Success result must have a value")
        if not self._success and self._error is None:
            raise ValueError("Failure result must have an error message")
    
    @classmethod
    def success(cls, value: T) -> 'Result[T]':
        """Создает успешный результат"""
        return cls(_success=True, _value=value)
    
    @classmethod
    def fail(cls, error: str) -> 'Result[T]':
        """Создает результат с ошибкой"""
        return cls(_success=False, _error=error)
    
    @property
    def is_success(self) -> bool:
        """Успех?"""
        return self._success
    
    @property
    def is_fail(self) -> bool:
        """Ошибка?"""
        return not self._success
    
    @property
    def value(self) -> T:
        """Получить значение"""
        if not self._success:
            raise ValueError(f"Cannot get value from failed result: {self._error}")
        return self._value
    
    @property
    def error(self) -> str:
        """Получить сообщение об ошибке"""
        if self._success:
            raise ValueError("Cannot get error from successful result")
        return self._error


@dataclass(frozen=True)
class Unit:
    """Для операций без возвращаемого значения (void)"""
    pass
