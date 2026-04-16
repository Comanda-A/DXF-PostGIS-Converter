# Проектирование пакета application/mappers

## Исходная диаграмма классов пакета «mappers»

```uml
@startuml

interface IMapper {
  + to_dto(entity: T): DTO
  + to_entity(dto: DTO): T
}

class DXFMapper {
  - logger: ILogger
  
  + to_dto(obj: DXFBase | List): DXFBaseDTO | List
  - _single_to_dto(obj: DXFBase): DXFBaseDTO
  - _document_to_dto(doc: DXFDocument): DXFDocumentDTO
  - _layer_to_dto(layer: DXFLayer): DXFLayerDTO
  - _entity_to_dto(entity: DXFEntity): DXFEntityDTO
  - _content_to_dto(content: DXFContent): Dict
}

class ConnectionConfigMapper {
  + to_dto(config: ConnectionConfig): ConnectionConfigDTO
  + to_entity(dto: ConnectionConfigDTO): ConnectionConfig
}

class ImportConfigMapper {
  + to_dto(config: ImportConfig): ImportConfigDTO
  + to_entity(dto: ImportConfigDTO): ImportConfig
}

IMapper <|.. DXFMapper : реализует
IMapper <|.. ConnectionConfigMapper : реализует
IMapper <|.. ImportConfigMapper : реализует

@enduml
```

---

## Описание классов пакета «mappers»

| Класс | Назначение | Тип |
|-------|-----------|-----|
| **IMapper** | Интерфейс для всех маппалов. Определяет преобразование Entity ↔ DTO. | interface |
| **DXFMapper** | Маппалаа DXF сущностей на DTOs. Рекурсивно преобразует иерархию: Document → Layers → Entities. | mapper |
| **ConnectionConfigMapper** | Маппалаа конфиго подключения между domain и application слоями. | mapper |
| **ImportConfigMapper** | Маппалаа конфиго импорта на DTO для использования в dialogs. | mapper |

---

## Диаграммы последовательностей взаимодействия объектов

### Нормальный ход событий: Преобразование документа с вложенной иерархией

```uml
@startuml

participant "Service" as Service
participant "DXFMapper" as Mapper
participant "DXFDocument" as Doc
participant "DXFLayer" as Layer
participant "DXFEntity" as Entity
participant "DTO" as DTO

-> Service: get_all()
activate Service

Service -> Mapper: to_dto(documents)
activate Mapper

alt List detected
  Mapper -> Mapper: iterate list
else Single object
  Mapper -> Mapper: process single
end

Mapper -> Doc: access document data
activate Doc
Doc --> Mapper: properties
deactivate Doc

Mapper -> Mapper: validate document

Mapper -> DTO: create DXFDocumentDTO
activate DTO

loop for each layer in document
  Mapper -> Layer: access layer data
  activate Layer
  Layer --> Mapper: properties
  deactivate Layer
  
  loop for each entity in layer
    Mapper -> Entity: access entity data
    activate Entity
    Entity --> Mapper: properties
    deactivate Entity
    
    Mapper -> Mapper: create EntityDTO
  end
  
  Mapper -> Mapper: create LayerDTO
end

DTO --> Mapper: created
deactivate DTO

Mapper --> Service: Result[DTO]
deactivate Mapper

<-- Service: DTOs
deactivate Service

@enduml
```

### Нормальный ход событий: Обратное преобразование конфига

```uml
@startuml

participant "Dialog" as Dialog
participant "ConnectionConfigMapper" as Mapper
participant "ConnectionConfigDTO" as DTO
participant "ConnectionConfig" as Entity

-> Dialog: save_connection()
activate Dialog

Dialog -> Dialog: collect form data
Dialog -> DTO: create with values
activate DTO

Dialog -> Mapper: to_entity(dto)
activate Mapper

Mapper -> Mapper: validate dto
Mapper -> Entity: create(values)
activate Entity

Entity --> Mapper: instance created
deactivate Entity

Mapper --> Dialog: Result[ConnectionConfig]
deactivate Mapper

Dialog -> Dialog: save config
deactivate DTO

deactivate Dialog

@enduml
```

### Прерывание процесса пользователем: Отмена маппирования

```uml
@startuml

participant "Service" as Service
participant "DXFMapper" as Mapper
participant "Entity" as Entity

-> Service: get_document_data()
activate Service

Service -> Mapper: to_dto(large_document)
activate Mapper

Mapper -> Mapper: processing entities...

loop for each entity
  Mapper -> Entity: access
  Entity --> Mapper: data
  
  -> Mapper: cancel_mapping()
  activate Mapper
  
  Mapper -> Mapper: cleanup partial result
  
  <-- Mapper: cancelled
  deactivate Mapper
end

Mapper --> Service: cancelled
deactivate Mapper

<-- Service: cancelled
deactivate Service

@enduml
```

### Прерывание процесса системой: Ошибка при маппировании невалидных данных

```uml
@startuml

participant "Mapper" as Mapper
participant "Entity" as Entity

-> Mapper: to_dto(entity)
activate Mapper

Mapper -> Entity: access geometry
activate Entity

Entity -> Entity: Invalid geometry data format

Entity --> Mapper: Exception

Mapper -> Mapper: log error: "Invalid entity data"

<-- Mapper: Result.fail(error)
deactivate Entity
deactivate Mapper

@enduml
```

---

## Уточненная диаграмма классов (с типами связей)

```uml
@startuml

interface IMapper {
  {abstract} + to_dto(entity: T): DTO
  {abstract} + to_entity(dto: DTO): T
}

class DXFMapper {
  - logger: ILogger
  
  + to_dto(obj: DXFBase | List):\nDXFBaseDTO | List[DXFBaseDTO]
  - _single_to_dto(obj: DXFBase): DXFBaseDTO
  - _document_to_dto(doc: DXFDocument): DXFDocumentDTO
  - _layer_to_dto(layer: DXFLayer): DXFLayerDTO
  - _entity_to_dto(entity: DXFEntity): DXFEntityDTO
  - _validate_entity(entity: DXFEntity): bool
  - _log_mapping(message: str): void
}

class ConnectionConfigMapper {
  + to_dto(config: ConnectionConfig): ConnectionConfigDTO
  + to_entity(dto: ConnectionConfigDTO): ConnectionConfig
  - _validate_config(config): bool
  - _encrypt_password(password: str): str
  - _decrypt_password(encrypted: str): str
}

class ImportConfigMapper {
  + to_dto(config: ImportConfig): ImportConfigDTO
  + to_entity(dto: ImportConfigDTO): ImportConfig
  - _resolve_filepath(path: str): str
  - _validate_mappings(mappings: dict): bool
}

IMapper <|.. DXFMapper
IMapper <|.. ConnectionConfigMapper
IMapper <|.. ImportConfigMapper

DXFMapper -- "many" DXFDocument : преобразует
ConnectionConfigMapper -- "1" ConnectionConfig : преобразует
ImportConfigMapper -- "1" ImportConfig : преобразует

@enduml
```

---

## Детальная диаграмма классов (все поля и методы)

```uml
@startuml

interface IMapper #CCCCCC {
  {abstract} + to_dto(entity: T) : DTO
  {abstract} + to_entity(dto: DTO) : T
}

class DXFMapper {
  - logger: ILogger
  
  + to_dto(obj: Union[DXFBase, List[DXFBase]],\nrecursive: bool = True)\n: Union[DXFBaseDTO, List[DXFBaseDTO]]
  + _single_to_dto(obj: DXFBase) : DXFBaseDTO
  - _document_to_dto(doc: DXFDocument) : DXFDocumentDTO
  - _layer_to_dto(layer: DXFLayer) : DXFLayerDTO
  - _entity_to_dto(entity: DXFEntity) : DXFEntityDTO
  - _content_to_dto(content: DXFContent) : Dict[str, Any]
  - _validate_entity(entity: DXFEntity) : bool
  - _extract_geometry_data(entity: DXFEntity) : Dict[str, Any]
  - _extract_attributes(entity: DXFEntity) : Dict[str, Any]
  - _log_mapping(message: str, level: str = 'info') : void
  - _check_type_consistency(entity: DXFBase,\nexpected_type: Type) : bool
}

class ConnectionConfigMapper {
  - encryption_key: Optional[str]
  - logger: ILogger
  
  + to_dto(config: ConnectionConfig) : ConnectionConfigDTO
  + to_entity(dto: ConnectionConfigDTO) : ConnectionConfig
  - _validate_config(config: ConnectionConfig) : bool
  - _validate_dto(dto: ConnectionConfigDTO) : bool
  - _encrypt_password(password: str) : str
  - _decrypt_password(encrypted: str) : str
  - _validate_host(host: str) : bool
  - _validate_port(port: int) : bool
  - _validate_database_name(name: str) : bool
  - _test_connection(config: ConnectionConfig) : bool
}

class ImportConfigMapper {
  - basepath: str
  - logger: ILogger
  
  + to_dto(config: ImportConfig) : ImportConfigDTO
  + to_entity(dto: ImportConfigDTO) : ImportConfig
  - _resolve_filepath(path: str) : str
  - _validate_config(config: ImportConfig) : bool
  - _validate_dto(dto: ImportConfigDTO) : bool
  - _validate_schema_names(layer_schema: str,\nfile_schema: str) : bool
  - _validate_mappings(mappings: Dict[str, str]) : bool
  - _resolve_import_mode(mode_str: str) : ImportMode
  - _build_field_mappings(config: ImportConfig) : Dict[str, str]
}

IMapper <|.. DXFMapper
IMapper <|.. ConnectionConfigMapper
IMapper <|.. ImportConfigMapper

@enduml
```

---

## Описание полей класса «DXFMapper»

| Поле | Тип | Модификатор | Описание |
|------|-----|-------------|---------|
| **logger** | ILogger | private | Логгер для отслеживания операций маппирования |

---

## Описание методов класса «DXFMapper»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **to_dto** | obj: Union[DXFBase, List[DXFBase]], recursive: bool = True | Union[DXFBaseDTO, List[DXFBaseDTO]] | Главный метод преобразования Entity в DTO (поддерживает списки) |
| **_single_to_dto** | obj: DXFBase | DXFBaseDTO | Внутренний метод для преобразования одного объекта |
| **_document_to_dto** | doc: DXFDocument | DXFDocumentDTO | Преобразует документ в DTO с рекурсивным маппингом слоев |
| **_layer_to_dto** | layer: DXFLayer | DXFLayerDTO | Преобразует слой в DTO с рекурсивным маппингом элементов |
| **_entity_to_dto** | entity: DXFEntity | DXFEntityDTO | Преобразует элемент в DTO |
| **_content_to_dto** | content: DXFContent | Dict[str, Any] | Преобразует содержимое в словарь |
| **_validate_entity** | entity: DXFEntity | bool | Проверяет корректность данных перед маппингом |
| **_extract_geometry_data** | entity: DXFEntity | Dict[str, Any] | Извлекает геометрические данные из entity |
| **_extract_attributes** | entity: DXFEntity | Dict[str, Any] | Извлекает атрибуты из entity |
| **_log_mapping** | message: str, level: str = 'info' | None | Логирует операции маппирования |
| **_check_type_consistency** | entity: DXFBase, expected_type: Type | bool | Проверяет соответствие типов |

---

## Описание полей класса «ConnectionConfigMapper»

| Поле | Тип | Модификатор | Описание |
|------|-----|-------------|---------|
| **encryption_key** | Optional[str] | private | Ключ для шифрования пароля (опционально) |
| **logger** | ILogger | private | Логгер для отслеживания преобразований |

---

## Описание методов класса «ConnectionConfigMapper»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **to_dto** | config: ConnectionConfig | ConnectionConfigDTO | Преобразует domain конфиг в DTO |
| **to_entity** | dto: ConnectionConfigDTO | ConnectionConfig | Преобразует DTO в domain entity |
| **_validate_config** | config: ConnectionConfig | bool | Проверяет domain конфиг перед маппингом |
| **_validate_dto** | dto: ConnectionConfigDTO | bool | Проверяет DTO перед маппингом в domain |
| **_encrypt_password** | password: str | str | Шифрует пароль для безопасного хранения |
| **_decrypt_password** | encrypted: str | str | Расшифровывает пароль |
| **_validate_host** | host: str | bool | Валидирует хост (IP или DNS) |
| **_validate_port** | port: int | bool | Валидирует номер порта (1-65535) |
| **_validate_database_name** | name: str | bool | Валидирует имя базы данных |
| **_test_connection** | config: ConnectionConfig | bool | Тестирует подключение перед сохранением |

---

## Описание полей класса «ImportConfigMapper»

| Поле | Тип | Модификатор | Описание |
|------|-----|-------------|---------|
| **basepath** | str | private | Базовая директория для разрешения относительных путей |
| **logger** | ILogger | private | Логгер для отслеживания маппирования |

---

## Описание методов класса «ImportConfigMapper»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **to_dto** | config: ImportConfig | ImportConfigDTO | Преобразует конфиг импорта в DTO |
| **to_entity** | dto: ImportConfigDTO | ImportConfig | Преобразует DTO в domain entity |
| **_resolve_filepath** | path: str | str | Разрешает относительный путь в абсолютный |
| **_validate_config** | config: ImportConfig | bool | Проверяет domain конфиг |
| **_validate_dto** | dto: ImportConfigDTO | bool | Проверяет DTO |
| **_validate_schema_names** | layer_schema: str, file_schema: str | bool | Валидирует имена схем БД |
| **_validate_mappings** | mappings: Dict[str, str] | bool | Проверяет маппинг полей |
| **_resolve_import_mode** | mode_str: str | ImportMode | Преобразует строку в перечисление режима |
| **_build_field_mappings** | config: ImportConfig | Dict[str, str] | Строит словарь маппинга полей |

---

## Заключение

Пакет **mappers** отвечает за трансформацию данных между слоями архитектуры. DXFMapper реализует паттерн Mapper для рекурсивного преобразования иерархии Entity → DTO, что позволяет полностью разделить внутреннее представление (Domain) от того, как данные передаются пользовательскому интерфейсу. Использование отдельных маппалов для каждого типа конфигурации обеспечивает гибкость и упрощает тестирование.
