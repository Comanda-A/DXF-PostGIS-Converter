# -*- coding: utf-8 -*-
"""
Result DTOs - результаты операций.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ValidationResult:
    """Результат валидации конфигурации."""
    
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, message: str) -> None:
        """Добавить ошибку."""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str) -> None:
        """Добавить предупреждение."""
        self.warnings.append(message)
    
    @property
    def has_warnings(self) -> bool:
        """Есть ли предупреждения."""
        return len(self.warnings) > 0


@dataclass
class ImportResult:
    """Результат операции импорта."""
    
    success: bool = False
    message: str = ""
    
    # Статистика
    files_imported: int = 0
    layers_imported: int = 0
    entities_imported: int = 0
    
    # Ошибки по слоям
    layer_errors: Dict[str, str] = field(default_factory=dict)
    
    # Путь к временному файлу (для очистки)
    temp_file_path: Optional[str] = None
    
    @classmethod
    def success_result(
        cls, 
        message: str, 
        files: int = 0, 
        layers: int = 0, 
        entities: int = 0
    ) -> 'ImportResult':
        """Создать успешный результат."""
        return cls(
            success=True,
            message=message,
            files_imported=files,
            layers_imported=layers,
            entities_imported=entities
        )
    
    @classmethod
    def error_result(cls, message: str) -> 'ImportResult':
        """Создать результат с ошибкой."""
        return cls(success=False, message=message)


@dataclass
class ExportResult:
    """Результат операции экспорта."""
    
    success: bool = False
    message: str = ""
    
    # Путь к экспортированному файлу
    output_path: Optional[str] = None
    
    # Статистика
    entities_exported: int = 0
    
    @classmethod
    def success_result(
        cls, 
        message: str, 
        output_path: str, 
        entities: int = 0
    ) -> 'ExportResult':
        """Создать успешный результат."""
        return cls(
            success=True,
            message=message,
            output_path=output_path,
            entities_exported=entities
        )
    
    @classmethod
    def error_result(cls, message: str) -> 'ExportResult':
        """Создать результат с ошибкой."""
        return cls(success=False, message=message)
