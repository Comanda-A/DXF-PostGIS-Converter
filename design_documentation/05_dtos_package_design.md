# Проектирование пакета application/dtos

## Исходная диаграмма классов пакета «dtos»

```uml
@startuml

class DXFBaseDTO {
  - id: UUID
  - selected: bool
}

class DXFDocumentDTO {
  - filename: str
  - filepath: str
  - layers: List[DXFLayerDTO]
  - upload_date: datetime
  - update_date: datetime
}

class DXFLayerDTO {
  - name: str
  - schema_name: str
  - table_name: str
  - entities: List[DXFEntityDTO]
}

class DXFEntityDTO {
  - entity_type: str
  - name: str
  - attributes: Dict[str, Any]
  - geometries: Dict[str, Any]
}

class ConnectionConfigDTO {
  - host: str
  - port: int
  - database: str
  - username: str
  - password: str
}

class ImportConfigDTO {
  - filepath: str
  - layer_schema: str
  - file_schema: str
  - mapping_mode: ImportMode
}

class ExportConfigDTO {
  - layer_name: str
  - output_filepath: str
  - export_mode: ExportMode
}

enum ImportMode {
  ALWAYS_OVERWRITE
  SKIP_IF_EXISTS
  MERGE_WITH_EXISTING
}

enum ExportMode {
  GEOMETRIES_ONLY
  WITH_ATTRIBUTES
  FULL_EXPORT
}

DXFBaseDTO <|-- DXFDocumentDTO : наследует
DXFBaseDTO <|-- DXFLayerDTO : наследует
DXFBaseDTO <|-- DXFEntityDTO : наследует

DXFDocumentDTO *-- "0.*" DXFLayerDTO : содержит
DXFLayerDTO *-- "0.*" DXFEntityDTO : содержит

ImportConfigDTO --> ImportMode : использует
ExportConfigDTO --> ExportMode : использует

@enduml
```

---

## Описание классов пакета «dtos»

| Класс | Назначение | Тип |
|-------|-----------|-----|
| **DXFBaseDTO** | Абстрактный базовый DTO для всех DXF объектов. Содержит id и флаг выделения. | data class |
| **DXFDocumentDTO** | DTO документа DXF для передачи между слоями. Содержит метаданные и список слоев. | data class |
| **DXFLayerDTO** | DTO слоя DXF. Содержит название, маппинг на БД, список элементов. | data class |
| **DXFEntityDTO** | DTO элемента DXF. Содержит тип, атрибуты, геометрию. | data class |
| **ConnectionConfigDTO** | DTO конфигурации подключения к БД. Параметры хоста, базы, авторизации. | data class |
| **ImportConfigDTO** | DTO конфигурации импорта файла. Параметры импорта, маршруты схем. | data class |
| **ExportConfigDTO** | DTO конфигурации экспорта. Выбор слоя, пути, режима экспорта. | data class |
| **ImportMode** | Перечисление режимов импорта (перезапись, пропуск, слияние). | enum |
| **ExportMode** | Перечисление режимов экспорта (только геометрия, с атрибутами, полный). | enum |

---

## Диаграммы последовательностей взаимодействия объектов

### Нормальный ход событий: Преобразование Entity в DTO

```uml
@startuml

participant "ActiveDocumentService" as Service
participant "DXFMapper" as Mapper
participant "DXFDocument" as Entity
participant "DXFDocumentDTO" as DTO

-> Service: get_all()
activate Service

Service -> Mapper: to_dto(documents)
activate Mapper

Mapper -> Entity: access properties
activate Entity

Mapper -> Mapper: create DXFDocumentDTO
Entity --> Mapper: properties

loop для каждого слоя
  Mapper -> Mapper: convert layer to DTO
  Mapper -> Mapper: convert entities to DTO
end

Mapper -> DTO: populate
deactivate Entity

Mapper --> Service: List[DXFDocumentDTO]
deactivate Mapper

<-- Service: Result[List[DTO]]
deactivate Service

@enduml
```

### Нормальный ход событий: Сборка конфига импорта

```uml
@startuml

participant "ImportDialog" as Dialog
participant "ImportConfigDTO" as ConfigDTO
participant "ImportMode" as Mode

-> Dialog: collect_import_config()
activate Dialog

Dialog -> Dialog: read filepath
Dialog -> Dialog: read layer_schema
Dialog -> Dialog: read file_schema
Dialog -> Dialog: read mapping_mode

Dialog -> Mode: ImportMode.from_string(mode_str)
activate Mode
Mode --> Dialog: ImportMode enum value
deactivate Mode

Dialog -> ConfigDTO: create(filepath, schema, mode)
activate ConfigDTO
ConfigDTO --> Dialog: instance
deactivate ConfigDTO

<-- Dialog: ImportConfigDTO
deactivate Dialog

@enduml
```

### Прерывание процесса пользователем: Отмена преобразования

```uml
@startuml

participant "Service" as Service
participant "Mapper" as Mapper
participant "DTO" as DTO

-> Service: get_all()
activate Service

Service -> Mapper: to_dto(documents)
activate Mapper

Mapper -> DTO: converting...

-> Service: cancel_operation()
activate Service

Service -> Mapper: cancel()
Mapper -> Mapper: interrupt conversion

<-- Service: cancelled
deactivate Service

Mapper --> Service: partial_result or error
deactivate Mapper

deactivate Service

@enduml
```

### Прерывание процесса системой: Ошибка валидации при создании DTO

```uml
@startuml

participant "Mapper" as Mapper
participant "ConfigDTO" as DTO

-> Mapper: create_config_dto(data)
activate Mapper

Mapper -> DTO: validate(data)
activate DTO

DTO -> DTO: check required fields
DTO -> DTO: validate port range
DTO -> DTO: validate database name

DTO -> DTO: Exception: Invalid port value

DTO --> Mapper: Result.fail(error)
deactivate DTO

<-- Mapper: Result.fail("Invalid configuration")
deactivate Mapper

@enduml
```

---

## Уточненная диаграмма классов (с типами связей)

```uml
@startuml

class DXFBaseDTO {
  - id: UUID
  - selected: bool
  
  + to_dict(): Dict
  + to_json(): str
}

class DXFDocumentDTO {
  - filename: str
  - filepath: str
  - layers: List[DXFLayerDTO]
  - upload_date: Optional[datetime]
  - update_date: Optional[datetime]
  
  + to_dict(): Dict
  + to_json(): str
  + get_total_entities_count(): int
}

class DXFLayerDTO {
  - name: str
  - schema_name: str
  - table_name: str
  - entities: List[DXFEntityDTO]
  
  + to_dict(): Dict
  + to_json(): str
  + get_entities_count(): int
}

class DXFEntityDTO {
  - entity_type: str
  - name: str
  - attributes: Dict[str, Any]
  - geometries: Dict[str, Any]
  
  + to_dict(): Dict
  + to_json(): str
}

class ConnectionConfigDTO {
  - host: str
  - port: int
  - database: str
  - username: str
  - password: str
  
  + validate(): bool
  + to_dict(): Dict
  + to_connection_string(): str
}

class ImportConfigDTO {
  - filepath: str
  - layer_schema: str
  - file_schema: str
  - mapping_mode: ImportMode
  
  + validate(): bool
  + to_dict(): Dict
}

class ExportConfigDTO {
  - layer_name: str
  - output_filepath: str
  - export_mode: ExportMode
  
  + validate(): bool
  + to_dict(): Dict
}

enum ImportMode {
  ALWAYS_OVERWRITE
  SKIP_IF_EXISTS
  MERGE_WITH_EXISTING
}

enum ExportMode {
  GEOMETRIES_ONLY
  WITH_ATTRIBUTES
  FULL_EXPORT
}

DXFBaseDTO <|-- DXFDocumentDTO
DXFBaseDTO <|-- DXFLayerDTO
DXFBaseDTO <|-- DXFEntityDTO

DXFDocumentDTO *-- "0.*" DXFLayerDTO : агрегирует
DXFLayerDTO *-- "0.*" DXFEntityDTO : агрегирует

ImportConfigDTO -- "1" ImportMode : зависимость (использует)
ExportConfigDTO -- "1" ExportMode : зависимость (использует)

@enduml
```

---

## Детальная диаграмма классов (все поля и методы)

```uml
@startuml

class DXFBaseDTO {
  # id: UUID
  # selected: bool
  
  + __init__(id: UUID, selected: bool = True)
  + id: UUID {{property}}
  + selected: bool {{property}}
  + to_dict() : Dict[str, Any]
  + to_json() : str
}

class DXFDocumentDTO {
  - filename: str
  - filepath: str
  - layers: List[DXFLayerDTO]
  - upload_date: Optional[datetime]
  - update_date: Optional[datetime]
  
  + __init__(id: UUID, selected: bool, filename: str,\nfilepath: str, layers: List[DXFLayerDTO] = None,\nupload_date: Optional[datetime] = None,\nupdate_date: Optional[datetime] = None)
  + filename: str {{property}}
  + filepath: str {{property}}
  + layers: List[DXFLayerDTO] {{property}}
  + upload_date: Optional[datetime] {{property}}
  + update_date: Optional[datetime] {{property}}
  + to_dict() : Dict[str, Any]
  + to_json() : str
  + get_total_entities_count() : int
  + validate() : bool
}

class DXFLayerDTO {
  - name: str
  - schema_name: str
  - table_name: str
  - entities: List[DXFEntityDTO]
  
  + __init__(id: UUID, selected: bool, name: str,\nschema_name: str = "", table_name: str = "",\nentities: List[DXFEntityDTO] = None)
  + name: str {{property}}
  + schema_name: str {{property}}
  + table_name: str {{property}}
  + entities: List[DXFEntityDTO] {{property}}
  + to_dict() : Dict[str, Any]
  + to_json() : str
  + get_entities_count() : int
  + validate() : bool
}

class DXFEntityDTO {
  - entity_type: str
  - name: str
  - attributes: Dict[str, Any]
  - geometries: Dict[str, Any]
  
  + __init__(id: UUID, selected: bool, entity_type: str,\nname: str = "", attributes: Dict[str, Any] = None,\ngeometries: Dict[str, Any] = None)
  + entity_type: str {{property}}
  + name: str {{property}}
  + attributes: Dict[str, Any] {{property}}
  + geometries: Dict[str, Any] {{property}}
  + to_dict() : Dict[str, Any]
  + to_json() : str
  + validate() : bool
}

class ConnectionConfigDTO {
  - host: str
  - port: int
  - database: str
  - username: str
  - password: str
  - ssl_mode: bool
  - timeout: int
  
  + __init__(host: str, port: int, database: str,\nusername: str, password: str,\nssl_mode: bool = False, timeout: int = 30)
  + host: str {{property}}
  + port: int {{property}}
  + database: str {{property}}
  + username: str {{property}}
  + password: str {{property}}
  + ssl_mode: bool {{property}}
  + timeout: int {{property}}
  + validate() : bool
  + to_dict() : Dict[str, Any]
  + to_connection_string() : str
  + __eq__(other: ConnectionConfigDTO) : bool
}

class ImportConfigDTO {
  - filepath: str
  - layer_schema: str
  - file_schema: str
  - mapping_mode: ImportMode
  - auto_cleanup: bool
  - field_mappings: Dict[str, str]
  
  + __init__(filepath: str, layer_schema: str,\nfile_schema: str = 'file_schema',\nmapping_mode: ImportMode = ImportMode.ALWAYS_OVERWRITE,\nauto_cleanup: bool = False,\nfield_mappings: Dict[str, str] = None)
  + filepath: str {{property}}
  + layer_schema: str {{property}}
  + file_schema: str {{property}}
  + mapping_mode: ImportMode {{property}}
  + auto_cleanup: bool {{property}}
  + field_mappings: Dict[str, str] {{property}}
  + validate() : bool
  + to_dict() : Dict[str, Any]
  - _validate_filepath() : bool
  - _validate_schema_names() : bool
}

class ExportConfigDTO {
  - layer_name: str
  - output_filepath: str
  - export_mode: ExportMode
  - include_attributes: bool
  - include_metadata: bool
  - coordinate_system: str
  
  + __init__(layer_name: str, output_filepath: str,\nexport_mode: ExportMode = ExportMode.FULL_EXPORT,\ninclude_attributes: bool = True,\ninclude_metadata: bool = True,\ncoordinate_system: str = "EPSG:4326")
  + layer_name: str {{property}}
  + output_filepath: str {{property}}
  + export_mode: ExportMode {{property}}
  + include_attributes: bool {{property}}
  + include_metadata: bool {{property}}
  + coordinate_system: str {{property}}
  + validate() : bool
  + to_dict() : Dict[str, Any]
  - _validate_layer_name() : bool
  - _validate_output_path() : bool
}

enum ImportMode {
  ALWAYS_OVERWRITE
  SKIP_IF_EXISTS
  MERGE_WITH_EXISTING
}

enum ExportMode {
  GEOMETRIES_ONLY
  WITH_ATTRIBUTES
  FULL_EXPORT
}

DXFBaseDTO <|-- DXFDocumentDTO
DXFBaseDTO <|-- DXFLayerDTO
DXFBaseDTO <|-- DXFEntityDTO

DXFDocumentDTO *-- "0.*" DXFLayerDTO
DXFLayerDTO *-- "0.*" DXFEntityDTO

ImportConfigDTO -- ImportMode
ExportConfigDTO -- ExportMode

@enduml
```

---

## Описание полей класса «DXFDocumentDTO»

| Поле | Тип | Описание |
|------|-----|---------|
| **filename** | str | Имя файла DXF (без пути) |
| **filepath** | str | Полный путь к файлу |
| **layers** | List[DXFLayerDTO] | Плоский список слоев (для UI отображения) |
| **upload_date** | Optional[datetime] | Дата загрузки в систему |
| **update_date** | Optional[datetime] | Дата последнего обновления |

---

## Описание методов класса «DXFDocumentDTO»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | id, selected, filename, filepath, layers, upload_date, update_date | None | Инициализирует DTO документа |
| **to_dict** | - | Dict[str, Any] | Преобразует DTO в словарь Python |
| **to_json** | - | str | Преобразует DTO в JSON строку |
| **get_total_entities_count** | - | int | Подсчитывает все элементы во всех слоях |
| **validate** | - | bool | Проверяет корректность данных DTO |

---

## Описание полей класса «ConnectionConfigDTO»

| Поле | Тип | Описание |
|------|-----|---------|
| **host** | str | Хост PostgreSQL сервера |
| **port** | int | Порт подключения (по умолчанию 5432) |
| **database** | str | Имя базы данных |
| **username** | str | Имя пользователя для авторизации |
| **password** | str | Пароль пользователя |
| **ssl_mode** | bool | Использование SSL шифрования |
| **timeout** | int | Таймаут подключения в секундах |

---

## Описание методов класса «ConnectionConfigDTO»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | host, port, database, username, password, ssl_mode, timeout | None | Инициализирует конфиг подключения |
| **validate** | - | bool | Проверяет валидность сетевых параметров |
| **to_dict** | - | Dict[str, Any] | Преобразует конфиг в словарь |
| **to_connection_string** | - | str | Генерирует строку подключения PostgreSQL |
| **__eq__** | other: ConnectionConfigDTO | bool | Сравнивает два конфига на равенство |

---

## Описание полей класса «ImportConfigDTO»

| Поле | Тип | Описание |
|------|-----|---------|
| **filepath** | str | Путь к DXF файлу для импорта |
| **layer_schema** | str | Имя схемы БД для слоев |
| **file_schema** | str | Имя схемы БД для файлов |
| **mapping_mode** | ImportMode | Режим импорта (перезапись, пропуск, слияние) |
| **auto_cleanup** | bool | Автоочистка временных файлов |
| **field_mappings** | Dict[str, str] | Маппинг полей из DXF на поля БД |

---

## Описание методов класса «ImportConfigDTO»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | filepath, layer_schema, file_schema, etc. | None | Инициализирует конфиг импорта |
| **validate** | - | bool | Проверяет корректность всех параметров |
| **to_dict** | - | Dict[str, Any] | Преобразует конфиг в словарь |
| **_validate_filepath** | - | bool | Проверяет существование файла |
| **_validate_schema_names** | - | bool | Проверяет допустимость имен схем |

---

## Описание полей класса «ExportConfigDTO»

| Поле | Тип | Описание |
|------|-----|---------|
| **layer_name** | str | Имя слоя в БД для экспорта |
| **output_filepath** | str | Путь к выходному DXF файлу |
| **export_mode** | ExportMode | Режим экспорта (геометрия, атрибуты, полный) |
| **include_attributes** | bool | Включить ли атрибуты элементов |
| **include_metadata** | bool | Включить ли метаданные слоя |
| **coordinate_system** | str | Система координат (EPSG код) |

---

## Описание методов класса «ExportConfigDTO»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | layer_name, output_filepath, export_mode, etc. | None | Инициализирует конфиг экспорта |
| **validate** | - | bool | Проверяет все параметры экспорта |
| **to_dict** | - | Dict[str, Any] | Преобразует конфиг в словарь |
| **_validate_layer_name** | - | bool | Проверяет имя слоя |
| **_validate_output_path** | - | bool | Проверяет валидность пути вывода |

---

## Описание перечисления «ImportMode»

| Значение | Описание |
|----------|---------|
| **ALWAYS_OVERWRITE** | Всегда перезаписывать существующие данные |
| **SKIP_IF_EXISTS** | Пропустить файл, если слой уже существует |
| **MERGE_WITH_EXISTING** | Слить новые данные с существующими |

---

## Описание перечисления «ExportMode»

| Значение | Описание |
|----------|---------|
| **GEOMETRIES_ONLY** | Экспортировать только геометрию без атрибутов |
| **WITH_ATTRIBUTES** | Экспортировать геометрию с атрибутами |
| **FULL_EXPORT** | Полный экспорт с метаданными и всеми данными |

---

## Заключение

Пакет **dtos** содержит структуры данных для передачи между слоями приложения. DTOs позволяют изолировать Domain entities от деталей Presentation слоя, обеспечивая чистоту архитектуры. Использование перечислений (Enums) для режимов импорта/экспорта обеспечивает типобезопасность и исключает ошибки от строк с опечатками.
