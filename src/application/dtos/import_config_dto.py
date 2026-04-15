
from dataclasses import dataclass
from ...application.dtos import ImportMode

@dataclass
class ImportConfigDTO:

    filename: str
    import_mode: ImportMode

    # Схемы
    layer_schema: str
    file_schema: str
    
    import_layers_only: bool = False    # Импортировать только слои
    