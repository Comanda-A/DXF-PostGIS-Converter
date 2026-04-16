# Проектирование пакета domain/entities

## Исходная диаграмма классов пакета «entities»

```uml
@startuml

class DXFBase {
  - id: UUID
  - selected: bool
  
  + id: UUID {{property}}
  + is_selected: bool {{property}}
  + set_selected(value: bool)
}

class DXFDocument {
  - filename: str
  - filepath: str
  - layers: Dict[UUID, DXFLayer]
  - content: DXFContent
  - upload_date: datetime
  - update_date: datetime
}

class DXFLayer {
  - document_id: UUID
  - name: str
  - schema_name: str
  - table_name: str
  - entities: Dict[UUID, DXFEntity]
}

class DXFEntity {
  - entity_type: DxfEntityType
  - name: str
  - attributes: Dict[str, Any]
  - geometries: Dict[str, Any]
  - extra_data: Dict[str, Any]
}

class DXFContent {
  - document_id: UUID
  - content: bytes
}

DXFBase <|-- DXFDocument : наследует
DXFBase <|-- DXFLayer : наследует
DXFBase <|-- DXFEntity : наследует
DXFBase <|-- DXFContent : наследует

DXFDocument *-- "0.*" DXFLayer : содержит
DXFDocument o-- "0..1" DXFContent : имеет
DXFLayer *-- "0.*" DXFEntity : содержит

@enduml
```

---

## Описание классов пакета «entities»

| Класс | Назначение | Тип |
|-------|-----------|-----|
| **DXFBase** | Абстрактный базовый класс для всех сущностей DXF. Определяет уникальный идентификатор UUID и флаг выделения объекта. | abstract |
| **DXFDocument** | Представляет DXF документ (файл). Содержит информацию о файле, список слоев и бинарное содержимое. Основной корневой объект иерархии. | entity |
| **DXFLayer** | Представляет слой DXF. Содержит список элементов (entities) и информацию о связи с таблицей в БД (schema_name, table_name). | entity |
| **DXFEntity** | Представляет элемент чертежа DXF (линия, круг, точка и т.д.). Содержит тип, атрибуты, геометрию и дополнительные данные. | entity |
| **DXFContent** | Представляет бинарное содержимое DXF файла. Хранит raw bytes документа для воспроизведения. | entity |

---

## Диаграммы последовательностей взаимодействия объектов

### Нормальный ход событий: Загрузка DXF документа

```uml
@startuml

participant "DXFReader" as Reader
participant "DXFDocument" as Document
participant "DXFLayer" as Layer
participant "DXFEntity" as Entity
participant "DXFContent" as Content

-> Reader: open(filepath)
activate Reader

Reader -> Document: create(filename, filepath)
activate Document
Document --> Reader: instance
deactivate Document

Reader -> Content: create(document_id, bytes)
activate Content
Content --> Reader: instance
deactivate Content

Reader -> Layer: create(document_id, name)
activate Layer
Layer --> Reader: instance
deactivate Layer

Reader -> Entity: create(entity_type, name, attributes)
activate Entity
Entity --> Reader: instance
deactivate Entity

Reader -> Layer: add_entity(entity)
activate Layer
Layer --> Reader: success
deactivate Layer

Reader -> Document: add_content(content)
activate Document
Document --> Reader: success
deactivate Document

Reader -> Document: add_layer(layer)
activate Document
Document --> Reader: success
deactivate Document

<-- Reader: Result[DXFDocument]
deactivate Reader

@enduml
```

### Нормальный ход событий: Удаление объекта из документа

```uml
@startuml

participant "User" as User
participant "DXFDocument" as Document
participant "DXFLayer" as Layer
participant "DXFEntity" as Entity

-> Document: remove_entity(entity_id)
activate Document

Document -> Layer: remove_entity(entity_id)
activate Layer

Layer -> Entity: verify_exists(entity_id)
activate Entity
Entity --> Layer: true
deactivate Entity

Layer -> Layer: delete entities[entity_id]
deactivate Layer

Document --> User: success
deactivate Document

@enduml
```

### Прерывание процесса пользователем: Отмена загрузки

```uml
@startuml

participant "User" as User
participant "DXFReader" as Reader
participant "DXFDocument" as Document
participant "DXFLayer" as Layer

-> Reader: open(filepath)
activate Reader

Reader -> Document: create()
activate Document
Document --> Reader: instance
deactivate Document

Reader -> Layer: create()
activate Layer
Layer --> Reader: instance
deactivate Layer

-> User: cancel_operation()
activate User

User -> Reader: cancel()
Reader -> Reader: Отмена процесса
Reader --> Document: cleanup
deactivate Document
Reader --> Layer: cleanup
deactivate Layer

<-- User: Operation cancelled
deactivate User
deactivate Reader

@enduml
```

### Прерывание процесса системой: Исключение при создании объекта

```uml
@startuml

participant "DXFReader" as Reader
participant "DXFDocument" as Document
participant "DXFLayer" as Layer
participant "DXFEntity" as Entity

-> Reader: open(invalid_filepath)
activate Reader

Reader -> Document: create(filename, filepath)
activate Document
Document --> Reader: instance
deactivate Document

Reader -> Layer: create(document_id, name)
activate Layer
Layer --> Reader: instance
deactivate Layer

Reader -> Entity: create(entity_type, ...)
activate Entity
Entity -> Entity: Ошибка валидации данных
Entity --> Layer: Exception
deactivate Entity

Layer --> Reader: Exception
deactivate Layer

<-- Reader: Result.fail(error)
deactivate Reader

@enduml
```

---

## Уточненная диаграмма классов (с типами связей)

```uml
@startuml

class DXFBase {
  # id: UUID
  # selected: bool
  
  + id: UUID {{property}}
  + is_selected: bool {{property}}
  + set_selected(value: bool)
}

class DXFDocument {
  - filename: str
  - filepath: str
  - layers: Dict[UUID, DXFLayer]
  - content: DXFContent
  - upload_date: datetime
  - update_date: datetime
  
  + filename: str {{property}}
  + filepath: str {{property}}
  + layers: Dict[UUID, DXFLayer] {{property}}
  + content: DXFContent {{property}}
  + add_layer(layer: DXFLayer)
  + remove_layer(layer_id: UUID)
  + add_content(content: DXFContent)
}

class DXFLayer {
  - document_id: UUID
  - name: str
  - schema_name: str
  - table_name: str
  - entities: Dict[UUID, DXFEntity]
  
  + document_id: UUID {{property}}
  + name: str {{property}}
  + schema_name: str {{property}}
  + table_name: str {{property}}
  + entities: Dict[UUID, DXFEntity] {{property}}
  + add_entity(entity: DXFEntity)
  + remove_entity(entity_id: UUID)
  + get_entities_count(): int
}

class DXFEntity {
  - entity_type: DxfEntityType
  - name: str
  - attributes: Dict[str, Any]
  - geometries: Dict[str, Any]
  - extra_data: Dict[str, Any]
  
  + entity_type: DxfEntityType {{property}}
  + name: str {{property}}
  + attributes: Dict[str, Any] {{property}}
  + geometries: Dict[str, Any] {{property}}
  + extra_data: Dict[str, Any] {{property}}
  + update_attributes(attributes: Dict[str, Any])
  + update_geometries(geometries: Dict[str, Any])
}

class DXFContent {
  - document_id: UUID
  - content: bytes
  
  + document_id: UUID {{property}}
  + content: bytes {{property}}
  + get_size(): int
}

DXFBase <|-- DXFDocument : наследует
DXFBase <|-- DXFLayer : наследует
DXFBase <|-- DXFEntity : наследует
DXFBase <|-- DXFContent : наследует

DXFDocument *-- "0.*" DXFLayer : агрегирует (постоянная зависимость)
DXFDocument -- "0..1" DXFContent : агрегирует (постоянная зависимость)
DXFLayer *-- "0.*" DXFEntity : агрегирует (постоянная зависимость)

@enduml
```

---

## Детальная диаграмма классов (все поля и методы)

```uml
@startuml

class DXFBase {
  # id: UUID
  # _selected: bool
  
  + __init__(id: Optional[UUID] = None, selected: bool = True)
  + id: UUID {{property}}
  + is_selected: bool {{property}}
  + set_selected(value: bool)
}

class DXFDocument {
  - _filename: str
  - _filepath: str
  - _layers: Dict[UUID, DXFLayer]
  - _content: Optional[DXFContent]
  - _upload_date: Optional[datetime]
  - _update_date: Optional[datetime]
  
  + __init__(id: Optional[UUID] = None, selected: bool = True,\nfilename: str = "", filepath: str = "",\nlayers: Optional[List[DXFLayer]] = None,\nupload_date: Optional[datetime] = None,\nupdate_date: Optional[datetime] = None,\ncontent: Optional[DXFContent] = None)
  + create(...) : DXFDocument {{staticmethod}}
  + filename: str {{property}}
  + filepath: str {{property}}
  + layers: Dict[UUID, DXFLayer] {{property}}
  + content: Optional[DXFContent] {{property}}
  + upload_date: Optional[datetime] {{property}}
  + update_date: Optional[datetime] {{property}}
  + get_layers_count() : int
  + validate() : bool
  + to_dict() : Dict
}

class DXFLayer {
  - _document_id: UUID
  - _name: str
  - _schema_name: str
  - _table_name: str
  - _entities: Dict[UUID, DXFEntity]
  
  + __init__(document_id: UUID, name: str,\nschema_name: str = "", table_name: str = "",\nid: Optional[UUID] = None, selected: bool = True,\nentities: Optional[List[DXFEntity]] = None)
  + create(...) : DXFLayer {{staticmethod}}
  + document_id: UUID {{property}}
  + name: str {{property}}
  + schema_name: str {{property}}
  + table_name: str {{property}}
  + entities: Dict[UUID, DXFEntity] {{property}}
  + get_entities_count() : int
  + get_entity_by_id(entity_id: UUID) : Optional[DXFEntity]
  + validate() : bool
  + to_dict() : Dict
}

class DXFEntity {
  - _entity_type: DxfEntityType
  - _name: str
  - _attributes: Dict[str, Any]
  - _geometries: Dict[str, Any]
  - _extra_data: Dict[str, Any]
  
  + __init__(id: Optional[UUID] = None, selected: bool = True,\nentity_type: DxfEntityType = DxfEntityType.UNKNOWN,\nname: str = "", attributes: Optional[Dict[str, Any]] = None,\ngeometries: Optional[Dict[str, Any]] = None,\nextra_data: Optional[Dict[str, Any]] = None)
  + create(...) : DXFEntity {{staticmethod}}
  + entity_type: DxfEntityType {{property}}
  + name: str {{property}}
  + attributes: Dict[str, Any] {{property}}
  + geometries: Dict[str, Any] {{property}}
  + extra_data: Dict[str, Any] {{property}}
  + update_attributes(attrs: Dict[str, Any])
  + update_geometries(geoms: Dict[str, Any])
  + get_geometry(key: str, default: Any = None) : Any
  + validate() : bool
  + to_dict() : Dict
}

class DXFContent {
  - _document_id: UUID
  - _content: bytes
  
  + __init__(document_id: UUID, content: bytes,\nid: Optional[UUID] = None)
  + create(...) : DXFContent {{staticmethod}}
  + document_id: UUID {{property}}
  + content: bytes {{property}}
  + get_size() : int
  + validate() : bool
  + to_dict() : Dict
}

DXFBase <|-- DXFDocument
DXFBase <|-- DXFLayer
DXFBase <|-- DXFEntity
DXFBase <|-- DXFContent

DXFDocument *-- "0.*" DXFLayer
DXFDocument -- "0..1" DXFContent
DXFLayer *-- "0.*" DXFEntity

@enduml
```

---

## Описание полей класса «DXFBase»

| Поле | Тип | Модификатор | Описание |
|------|-----|-------------|---------|
| **id** | UUID | protected | Уникальный идентификатор объекта, генерируется автоматически при создании |
| **_selected** | bool | private | Флаг выделения объекта для пользовательского взаимодействия |

---

## Описание методов класса «DXFBase»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | id: Optional[UUID] = None, selected: bool = True | None | Конструктор базового класса. Инициализирует UUID и флаг выделения |
| **id** | - | UUID (property) | Получает уникальный идентификатор объекта |
| **is_selected** | - | bool (property) | Получает текущее состояние флага выделения |
| **set_selected** | value: bool | None | Устанавливает флаг выделения объекта |

---

## Описание полей класса «DXFDocument»

| Поле | Тип | Модификатор | Описание |
|------|-----|-------------|---------|
| **_filename** | str | private | Имя файла DXF (без пути) |
| **_filepath** | str | private | Полный путь к файлу DXF |
| **_layers** | Dict[UUID, DXFLayer] | private | Словарь слоев (ключ - UUID слоя) |
| **_content** | Optional[DXFContent] | private | Бинарное содержимое файла |
| **_upload_date** | Optional[datetime] | private | Дата загрузки документа в систему |
| **_update_date** | Optional[datetime] | private | Дата последнего обновления документа |

---

## Описание методов класса «DXFDocument»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | id: Optional[UUID], selected: bool, filename: str, filepath: str, layers: Optional[List[DXFLayer]], upload_date: Optional[datetime], update_date: Optional[datetime], content: Optional[DXFContent] | None | Инициализирует документ с параметрами |
| **create** | *args (как __init__) | DXFDocument | Factory метод для создания документа (паттерн Factory) |
| **filename** | - | str (property) | Получает имя файла |
| **filepath** | - | str (property) | Получает путь к файлу |
| **layers** | - | Dict[UUID, DXFLayer] (property) | Получает словарь слоев |
| **content** | - | Optional[DXFContent] (property) | Получает содержимое документа |
| **upload_date** | - | Optional[datetime] (property) | Получает дату загрузки |
| **update_date** | - | Optional[datetime] (property) | Получает дату обновления |
| **get_layers_count** | - | int | Возвращает количество слоев в документе |
| **validate** | - | bool | Проверяет корректность данных документа |
| **to_dict** | - | Dict | Преобразует объект в словарь (сериализация) |

---

## Описание полей класса «DXFLayer»

| Поле | Тип | Модификатор | Описание |
|------|-----|-------------|---------|
| **_document_id** | UUID | private | UUID документа-родителя |
| **_name** | str | private | Название слоя |
| **_schema_name** | str | private | Имя схемы в БД для этого слоя |
| **_table_name** | str | private | Имя таблицы в БД для этого слоя |
| **_entities** | Dict[UUID, DXFEntity] | private | Словарь элементов слоя (ключ - UUID элемента) |

---

## Описание методов класса «DXFLayer»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | document_id: UUID, name: str, schema_name: str, table_name: str, id: Optional[UUID], selected: bool, entities: Optional[List[DXFEntity]] | None | Инициализирует слой с параметрами |
| **create** | *args (как __init__) | DXFLayer | Factory метод для создания слоя |
| **document_id** | - | UUID (property) | Получает UUID документа-родителя |
| **name** | - | str (property) | Получает название слоя |
| **schema_name** | - | str (property) | Получает имя схемы БД |
| **table_name** | - | str (property) | Получает имя таблицы БД |
| **entities** | - | Dict[UUID, DXFEntity] (property) | Получает словарь элементов |
| **get_entities_count** | - | int | Возвращает количество элементов в слое |
| **get_entity_by_id** | entity_id: UUID | Optional[DXFEntity] | Получает элемент по UUID |
| **validate** | - | bool | Проверяет корректность данных слоя |
| **to_dict** | - | Dict | Преобразует слой в словарь |

---

## Описание полей класса «DXFEntity»

| Поле | Тип | Модификатор | Описание |
|------|-----|-------------|---------|
| **_entity_type** | DxfEntityType | private | Тип элемента (LINE, CIRCLE, POINT и т.д.) |
| **_name** | str | private | Название элемента |
| **_attributes** | Dict[str, Any] | private | Словарь атрибутов элемента (цвет, слой и т.д.) |
| **_geometries** | Dict[str, Any] | private | Словарь геометрических данных (координаты и т.д.) |
| **_extra_data** | Dict[str, Any] | private | Дополнительные данные элемента |

---

## Описание методов класса «DXFEntity»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | id: Optional[UUID], selected: bool, entity_type: DxfEntityType, name: str, attributes: Optional[Dict[str, Any]], geometries: Optional[Dict[str, Any]], extra_data: Optional[Dict[str, Any]] | None | Инициализирует элемент с параметрами |
| **create** | *args (как __init__) | DXFEntity | Factory метод для создания элемента |
| **entity_type** | - | DxfEntityType (property) | Получает тип элемента |
| **name** | - | str (property) | Получает название элемента |
| **attributes** | - | Dict[str, Any] (property) | Получает атрибуты элемента |
| **geometries** | - | Dict[str, Any] (property) | Получает геометрические данные |
| **extra_data** | - | Dict[str, Any] (property) | Получает дополнительные данные |
| **update_attributes** | attrs: Dict[str, Any] | None | Обновляет атрибуты элемента |
| **update_geometries** | geoms: Dict[str, Any] | None | Обновляет геометрические данные |
| **get_geometry** | key: str, default: Any = None | Any | Получает конкретное геометрическое значение |
| **validate** | - | bool | Проверяет корректность данных |
| **to_dict** | - | Dict | Преобразует элемент в словарь |

---

## Описание полей класса «DXFContent»

| Поле | Тип | Модификатор | Описание |
|------|-----|-------------|---------|
| **_document_id** | UUID | private | UUID документа-родителя |
| **_content** | bytes | private | Бинарные данные содержимого DXF файла |

---

## Описание методов класса «DXFContent»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | document_id: UUID, content: bytes, id: Optional[UUID] | None | Инициализирует содержимое документа |
| **create** | *args (как __init__) | DXFContent | Factory метод для создания содержимого |
| **document_id** | - | UUID (property) | Получает UUID документа-родителя |
| **content** | - | bytes (property) | Получает бинарное содержимое |
| **get_size** | - | int | Возвращает размер содержимого в байтах |
| **validate** | - | bool | Проверяет корректность бинарных данных |
| **to_dict** | - | Dict | Преобразует объект в словарь |

---

## Заключение

Пакет **entities** содержит основные сущности предметной области с чистой архитектурой, свободной от фреймворк-зависимостей. Иерархия наследования через `DXFBase` обеспечивает единообразное управление идентификаторами и состоянием выделения. Агрегирующие отношения создают древовидную структуру: документ → слои → элементы.
