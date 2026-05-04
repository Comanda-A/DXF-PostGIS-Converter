# 5.2.1. Проектирование классов пакета «entities»

Пакет «entities» содержит доменную модель DXF-документа: базовую сущность, сам документ, слой, элемент чертежа и бинарное содержимое.

## 5.2.1.1. Исходная диаграмма классов

Исходная диаграмма содержит только классы пакета `domain/entities`. Параметры классов не отображаются.

```mermaid
---
config:
    layout: elk
---
graph LR
    DXFBase
    DXFDocument
    DXFLayer
    DXFEntity
    DXFContent

    DXFBase -.->|наследует| DXFDocument
    DXFBase -.->|наследует| DXFLayer
    DXFBase -.->|наследует| DXFEntity
    DXFBase -.->|наследует| DXFContent

    DXFDocument -->|создает| DXFLayer
    DXFDocument -->|использует| DXFContent
    DXFLayer -->|создает| DXFEntity
    DXFLayer -->|связан по document_id| DXFDocument
    DXFContent -->|связан по document_id| DXFDocument
```

### Таблица 1. Описание классов пакета «entities»

| Класс | Описание |
|---|---|
| DXFBase | Базовый абстрактный класс для всех DXF-сущностей. |
| DXFDocument | Корневой объект DXF-документа. |
| DXFLayer | Слой DXF-документа. |
| DXFEntity | Элемент DXF-черчения. |
| DXFContent | Бинарное содержимое DXF-документа. |

## 5.2.1.2. Диаграммы последовательностей взаимодействия объектов классов

На диаграммах показано взаимодействие всех классов пакета. Внешние сущности не используются.

```mermaid
sequenceDiagram
    participant Entry as 
    participant Base as DXFBase
    participant Document as DXFDocument
    participant Layer as DXFLayer
    participant Entity as DXFEntity
    participant Content as DXFContent

        Entry->>Document: create(filename, filepath, layers, content)
        activate Document
        Document->>Base: __init__(id, selected)
        activate Base
        Base-->>Document: common state ready
        deactivate Base
        Document-->>Entry: instance
        deactivate Document

        Entry->>Content: create(document_id, bytes)
        activate Content
        Content->>Base: __init__(id, selected)
        activate Base
        Base-->>Content: common state ready
        deactivate Base
        Content-->>Entry: instance
        deactivate Content

        Entry->>Layer: create(document_id, name, schema_name, table_name)
        activate Layer
        Layer->>Base: __init__(id, selected)
        activate Base
        Base-->>Layer: common state ready
        deactivate Base
        Layer-->>Entry: instance
        deactivate Layer

        Entry->>Entity: create(entity_type, name, attributes, geometries, extra_data)
        activate Entity
        Entity->>Base: __init__(id, selected)
        activate Base
        Base-->>Entity: common state ready
        deactivate Base
        Entity-->>Entry: instance
        deactivate Entity        
```

```mermaid
sequenceDiagram
    participant Entry as ""
    participant Base as DXFBase
    participant Document as DXFDocument
    participant Layer as DXFLayer
    participant Entity as DXFEntity
    participant Content as DXFContent

    alt Прерывание пользователем
        Entry->>Document: create(filename, filepath)
        activate Document
        Document->>Base: __init__(id, selected)
        activate Base
        Base-->>Document: common state ready
        deactivate Base
        Document-->>Entry: instance
        deactivate Document

        Entry->>Layer: create(document_id, name)
        activate Layer
        Layer->>Base: __init__(id, selected)
        activate Base
        Base-->>Layer: common state ready
        deactivate Base
        Layer-->>Entry: instance
        deactivate Layer

        Entry->>Entity: create(entity_type, name)
        activate Entity
        Entity->>Base: __init__(id, selected)
        activate Base
        Base-->>Entity: common state ready
        deactivate Base
        Entity-->>Entry: instance
        deactivate Entity

        Entry->>Content: create(document_id, bytes)
        activate Content
        Content->>Base: __init__(id, selected)
        activate Base
        Base-->>Content: common state ready
        deactivate Base
        Content-->>Entry: instance
        deactivate Content

        Entry->>Document: cancel_operation()
        activate Document
        Document->>Layer: clear(recursive=True)
        Document->>Content: clear()
        Document->>Base: set_selected(False)
        Document-->>Entry: cleanup completed
        deactivate Document
    end
```

```mermaid
sequenceDiagram
    participant Entry as ""
    participant Base as DXFBase
    participant Document as DXFDocument
    participant Layer as DXFLayer
    participant Entity as DXFEntity
    participant Content as DXFContent

    alt Системное прерывание
        Entry->>Document: create(filename, filepath)
        activate Document
        Document->>Base: __init__(id, selected)
        activate Base
        Base-->>Document: common state ready
        deactivate Base
        Document-->>Entry: instance
        deactivate Document

        Entry->>Content: create(document_id, bytes)
        activate Content
        Content->>Base: __init__(id, selected)
        activate Base
        Base-->>Content: common state ready
        deactivate Base
        Content-->>Entry: instance
        deactivate Content

        Entry->>Layer: create(document_id, name, schema_name, table_name)
        activate Layer
        Layer->>Base: __init__(id, selected)
        activate Base
        Base-->>Layer: common state ready
        deactivate Base
        Layer-->>Entry: instance
        deactivate Layer

        Entry->>Entity: create(entity_type, name, attributes, geometries, extra_data)
        activate Entity
        Entity->>Base: __init__(id, selected)
        activate Base
        Base-->>Entity: common state ready
        deactivate Base
        Entity->>Entity: validation error
        Entity--x Layer: Result.fail(validation_error)
        deactivate Entity

        Layer->>Content: cleanup_failed_content()
        activate Content
        Content-->>Layer: success
        deactivate Content

        Layer->>Document: propagate_error(validation_error)
        activate Document
        Document->>Layer: clear(recursive=True)
        Document->>Content: clear()
        Document->>Base: set_selected(False)
        Document-->>Entry: Result.fail(validation_error)
        deactivate Document
    end
```

## 5.2.1.3. Уточненная диаграмма классов

Уточненная диаграмма показывает типы связей внутри пакета.

```mermaid
---
config:
    layout: elk
---
classDiagram
    orientation LR
    class DXFBase
    class DXFDocument
    class DXFLayer
    class DXFEntity
    class DXFContent

    DXFBase <|-- DXFDocument : наследует
    DXFBase <|-- DXFLayer : наследует
    DXFBase <|-- DXFEntity : наследует
    DXFBase <|-- DXFContent : наследует

    DXFDocument *-- "0.*" DXFLayer : создает
    DXFDocument o-- "0..1" DXFContent : использует
    DXFLayer *-- "0.*" DXFEntity : создает
    DXFLayer --> DXFDocument : связан по document_id
    DXFContent --> DXFDocument : связан по document_id
```

## 5.2.1.4. Детальная диаграмма классов

```mermaid
---
config:
    layout: elk
---
classDiagram
    class DXFBase {
        -_id: UUID
        -_selected: bool
        +__init__(id: UUID \| None, selected: bool)
        +id UUID
        +is_selected bool
        +set_selected(value: bool)
    }

    class DXFDocument {
        -_filename: str
        -_filepath: str
        -_layers: Dict[UUID, DXFLayer]
        -_content: DXFContent \| None
        -_upload_date: datetime \| None
        -_update_date: datetime \| None
        +__init__(id: UUID \| None, selected: bool, filename: str, filepath: str, layers: list[DXFLayer] \| None, upload_date: datetime \| None, update_date: datetime \| None, content: DXFContent \| None)
        +create(id: UUID \| None, selected: bool, filename: str, filepath: str, layers: list[DXFLayer] \| None, upload_date: datetime \| None, update_date: datetime \| None, content: DXFContent \| None) DXFDocument
        +filename str
        +filepath str
        +layers Dict[UUID, DXFLayer]
        +upload_date datetime \| None
        +update_date datetime \| None
        +content DXFContent \| None
        +add_content(content: DXFContent)
        +add_layers(layers: list[DXFLayer])
        +get_layer_by_id(layer_id: UUID) DXFLayer \| None
        +get_layer_by_name(name: str) DXFLayer \| None
        +remove_layer(layer: DXFLayer, recursive: bool) bool
        +clear()
    }

    class DXFLayer {
        -_document_id: UUID
        -_name: str
        -_schema_name: str
        -_table_name: str
        -_entities: Dict[UUID, DXFEntity]
        +__init__(document_id: UUID, name: str, schema_name: str, table_name: str, id: UUID \| None, selected: bool, entities: list[DXFEntity] \| None)
        +create(document_id: UUID, name: str, schema_name: str, table_name: str, id: UUID \| None, selected: bool, entities: list[DXFEntity] \| None) DXFLayer
        +document_id UUID
        +name str
        +schema_name str
        +table_name str
        +entities Dict[UUID, DXFEntity]
        +add_entities(entities: list[DXFEntity])
        +find_entity_by_id(entity_id: UUID) DXFEntity \| None
        +find_entity_by_name(name: str) DXFEntity \| None
        +clear(recursive: bool)
    }

    class DXFEntity {
        -_entity_type: DxfEntityType
        -_name: str
        -_attributes: Dict[str, Any]
        -_geometries: Dict[str, Any]
        -_extra_data: Dict[str, Any]
        +__init__(id: UUID \| None, selected: bool, entity_type: DxfEntityType, name: str, attributes: Dict[str, Any] \| None, geometries: Dict[str, Any] \| None, extra_data: Dict[str, Any] \| None)
        +create(id: UUID \| None, selected: bool, entity_type: DxfEntityType, name: str, attributes: Dict[str, Any] \| None, geometries: Dict[str, Any] \| None, extra_data: Dict[str, Any] \| None) DXFEntity
        +entity_type DxfEntityType
        +name str
        +attributes Dict[str, Any]
        +geometries Dict[str, Any]
        +extra_data Dict[str, Any]
        +add_attributes(attributes: Dict[str, Any])
        +add_geometries(geometries: Dict[str, Any])
        +add_extra_data(extra_data: Dict[str, Any])
        +clear(recursive: bool)
    }

    class DXFContent {
        -_document_id: UUID
        -_content: bytes
        +__init__(document_id: UUID, content: bytes, id: UUID \| None)
        +create(document_id: UUID, content: bytes, id: UUID \| None) DXFContent
        +document_id UUID
        +content bytes
    }

    DXFBase <|-- DXFDocument : наследует
    DXFBase <|-- DXFLayer : наследует
    DXFBase <|-- DXFEntity : наследует
    DXFBase <|-- DXFContent : наследует

    DXFDocument "1" *-- "0.*" DXFLayer : создает
    DXFDocument "1" o-- "0..1" DXFContent : использует
    DXFLayer "1" *-- "0.*" DXFEntity : создает
    DXFLayer "*" --> "1" DXFDocument : связан по document_id
    DXFContent "*" --> "1" DXFDocument : связан по document_id
```

## 5.2.1.5. Таблицы полей и методов

Детальная диаграмма включает поля и методы всех классов пакета `entities`.

### Класс DXFBase

#### Описание полей класса

| Название | Тип | Описание |
|---|---|---|
| _id | UUID | Уникальный идентификатор объекта |
| _selected | bool | Флаг выделения объекта |

#### Описание методов класса

| Название | Параметры | Возвращает | Описание |
|---|---|---|---|
| __init__ | `id: UUID \| None`, `selected: bool` | None | Инициализирует базовое состояние объекта |
| id | - | `UUID` | Возвращает идентификатор объекта |
| is_selected | - | `bool` | Возвращает признак выделения |
| set_selected | `value: bool` | None | Изменяет признак выделения |

### Класс DXFDocument

#### Описание полей класса

| Название | Тип | Описание |
|---|---|---|
| _filename | str | Имя файла DXF |
| _filepath | str | Путь к файлу DXF |
| _layers | Dict[UUID, DXFLayer] | Набор слоев документа |
| _content | DXFContent \| None | Бинарное содержимое документа |
| _upload_date | datetime \| None | Дата загрузки |
| _update_date | datetime \| None | Дата обновления |

#### Описание методов класса

| Название | Параметры | Возвращает | Описание |
|---|---|---|---|
| __init__ | `id: UUID \| None`, `selected: bool`, `filename: str`, `filepath: str`, `layers: list[DXFLayer] \| None`, `upload_date: datetime \| None`, `update_date: datetime \| None`, `content: DXFContent \| None` | None | Инициализирует документ и коллекцию слоев |
| create | те же параметры, что и `__init__` | `DXFDocument` | Фабричный метод создания документа |
| filename | - | `str` | Возвращает имя файла |
| filepath | - | `str` | Возвращает путь к файлу |
| layers | - | `Dict[UUID, DXFLayer]` | Возвращает слои документа |
| upload_date | - | `datetime \| None` | Возвращает дату загрузки |
| update_date | - | `datetime \| None` | Возвращает дату обновления |
| content | - | `DXFContent \| None` | Возвращает содержимое документа |
| add_content | `content: DXFContent` | None | Связывает документ с содержимым |
| add_layers | `layers: list[DXFLayer]` | None | Добавляет слои в документ |
| get_layer_by_id | `layer_id: UUID` | `DXFLayer \| None` | Получает слой по идентификатору |
| get_layer_by_name | `name: str` | `DXFLayer \| None` | Получает слой по имени |
| remove_layer | `layer: DXFLayer`, `recursive: bool = False` | `bool` | Удаляет слой из документа |
| clear | - | None | Очищает документ |

### Класс DXFLayer

#### Описание полей класса

| Название | Тип | Описание |
|---|---|---|
| _document_id | UUID | Идентификатор документа-владельца |
| _name | str | Имя слоя |
| _schema_name | str | Имя схемы БД |
| _table_name | str | Имя таблицы БД |
| _entities | Dict[UUID, DXFEntity] | Набор сущностей слоя |

#### Описание методов класса

| Название | Параметры | Возвращает | Описание |
|---|---|---|---|
| __init__ | `document_id: UUID`, `name: str`, `schema_name: str`, `table_name: str`, `id: UUID \| None`, `selected: bool`, `entities: list[DXFEntity] \| None` | None | Инициализирует слой и набор сущностей |
| create | те же параметры, что и `__init__` | `DXFLayer` | Фабричный метод создания слоя |
| document_id | - | `UUID` | Возвращает идентификатор документа |
| name | - | `str` | Возвращает имя слоя |
| schema_name | - | `str` | Возвращает имя схемы |
| table_name | - | `str` | Возвращает имя таблицы |
| entities | - | `Dict[UUID, DXFEntity]` | Возвращает сущности слоя |
| add_entities | `entities: list[DXFEntity]` | None | Добавляет сущности в слой |
| find_entity_by_id | `entity_id: UUID` | `DXFEntity \| None` | Получает сущность по идентификатору |
| find_entity_by_name | `name: str` | `DXFEntity \| None` | Получает сущность по имени |
| clear | `recursive: bool = True` | None | Очищает слой |

### Класс DXFEntity

#### Описание полей класса

| Название | Тип | Описание |
|---|---|---|
| _entity_type | DxfEntityType | Тип DXF-сущности |
| _name | str | Имя сущности |
| _attributes | Dict[str, Any] | Атрибуты сущности |
| _geometries | Dict[str, Any] | Геометрия сущности |
| _extra_data | Dict[str, Any] | Дополнительные данные сущности |

#### Описание методов класса

| Название | Параметры | Возвращает | Описание |
|---|---|---|---|
| __init__ | `id: UUID \| None`, `selected: bool`, `entity_type: DxfEntityType`, `name: str`, `attributes: Dict[str, Any] \| None`, `geometries: Dict[str, Any] \| None`, `extra_data: Dict[str, Any] \| None` | None | Инициализирует элемент чертежа |
| create | те же параметры, что и `__init__` | `DXFEntity` | Фабричный метод создания сущности |
| entity_type | - | `DxfEntityType` | Возвращает тип сущности |
| name | - | `str` | Возвращает имя сущности |
| attributes | - | `Dict[str, Any]` | Возвращает атрибуты сущности |
| geometries | - | `Dict[str, Any]` | Возвращает геометрию сущности |
| extra_data | - | `Dict[str, Any]` | Возвращает дополнительные данные |
| add_attributes | `attributes: Dict[str, Any]` | None | Дополняет атрибуты сущности |
| add_geometries | `geometries: Dict[str, Any]` | None | Дополняет геометрию сущности |
| add_extra_data | `extra_data: Dict[str, Any]` | None | Дополняет дополнительные данные |
| clear | `recursive: bool = True` | None | Очищает сущность |

### Класс DXFContent

#### Описание полей класса

| Название | Тип | Описание |
|---|---|---|
| _document_id | UUID | Идентификатор документа-владельца |
| _content | bytes | Бинарное содержимое файла |

#### Описание методов класса

| Название | Параметры | Возвращает | Описание |
|---|---|---|---|
| __init__ | `document_id: UUID`, `content: bytes`, `id: UUID \| None` | None | Инициализирует объект бинарного содержимого |
| create | `document_id: UUID`, `content: bytes`, `id: UUID \| None` | `DXFContent` | Фабричный метод создания содержимого |
| document_id | - | `UUID` | Возвращает идентификатор документа |
| content | - | `bytes` | Возвращает бинарное содержимое |
