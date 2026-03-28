
from dataclasses import dataclass
from ...application.dtos import ExportMode

@dataclass
class ExportConfigDTO:
    """Конфигурация экспорта PostGIS → DXF."""
    
    # Имя файла в БД
    filename: str = ''
    
    # Место назначения: "file" или "qgis"
    export_mode: ExportMode = ExportMode.FILE
    
    # Путь для сохранения
    output_path: str = ''
    
    # Схема файлов
    file_schema: str = 'file_schema'
    
    @property
    def is_valid(self) -> bool:
        return (
            (self.export_mode == ExportMode.FILE and self.filename) or
            self.export_mode == ExportMode.QGIS
        )
