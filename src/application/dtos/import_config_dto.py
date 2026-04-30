
from dataclasses import dataclass, field
from ...application.dtos import ImportMode

@dataclass
class LayerSettingsDTO:
    """DTO для хранения настроек отдельного слоя"""
    layer_name: str
    create_new_table: bool = True  # По умолчанию создавать новую таблицу
    new_table_name: str = ""  # Название новой таблицы (по умолчанию = layer_name)
    existing_table_name: str = ""  # Название существующей таблицы для импорта

@dataclass
class ImportConfigDTO:

    filename: str
    import_mode: ImportMode

    # Схемы
    layer_schema: str
    file_schema: str
    
    # Настройки файла
    import_layers_only: bool = False    # Импортировать только слои
    transliterate_layer_names: bool = False  # Транслитерировать русские названия слоев в английские
    prefix_check: bool = True  # Добавить префикс в названии слоя
    
    # Настройки слоев (ключ - название слоя, значение - настройки слоя)
    layer_settings: dict[str, LayerSettingsDTO] = field(default_factory=dict)
    