# Проектирование пакета domain/repositories

## Исходная диаграмма классов пакета «repositories»

```uml
@startuml

interface IRepository {
  + save(entity: T): Result[Unit]
  + find_by_id(id: UUID): Result[Optional[T]]
  + delete_by_id(id: UUID): Result[Unit]
  + find_all(): Result[List[T]]
}

interface IDocumentRepository {
  + save_document(doc: DXFDocument): Result[Unit]
  + find_document(id: UUID): Result[Optional[DXFDocument]]
  + find_all_documents(): Result[List[DXFDocument]]
  + delete_document(id: UUID): Result[Unit]
}

interface ILayerRepository {
  + save_layer(layer: DXFLayer): Result[Unit]
  + find_layers_by_document(doc_id: UUID): Result[List[DXFLayer]]
  + delete_layer(layer_id: UUID): Result[Unit]
}

interface IEntityRepository {
  + save_entity(entity: DXFEntity): Result[Unit]
  + find_entities_by_layer(layer_id: UUID): Result[List[DXFEntity]]
  + delete_entity(entity_id: UUID): Result[Unit]
}

interface IContentRepository {
  + save_content(content: DXFContent): Result[Unit]
  + find_content(doc_id: UUID): Result[Optional[DXFContent]]
  + delete_content(content_id: UUID): Result[Unit]
}

interface IActiveDocumentRepository {
  + get_all(): Result[List[DXFDocument]]
  + get_by_id(id: UUID): Result[Optional[DXFBase]]
  + get_by_filename(filename: str): Result[Optional[DXFDocument]]
  + add_active_document(doc: DXFDocument): Result[Unit]
  + remove_active_document(doc_id: UUID): Result[Unit]
}

interface IConnection {
  + open(): Result[Unit]
  + close(): Result[Unit]
  + is_connected(): bool
  + execute_query(query: str): Result[Any]
}

interface IConnectionFactory {
  + create_connection(config: ConnectionConfig): Result[IConnection]
}

interface IRepositoryFactory {
  + create_document_repository(): IDocumentRepository
  + create_layer_repository(): ILayerRepository
  + create_entity_repository(): IEntityRepository
  + create_content_repository(): IContentRepository
  + create_active_document_repository(): IActiveDocumentRepository
}

IRepository <|-- IDocumentRepository : специализирует
IRepository <|-- ILayerRepository : специализирует
IRepository <|-- IEntityRepository : специализирует
IRepository <|-- IContentRepository : специализирует

IActive DocumentRepository --> "many" DXFDocument : управляет
IDocumentRepository --> "many" DXFDocument : работает с
ILayerRepository --> "many" DXFLayer : работает с
IEntityRepository --> "many" DXFEntity : работает с
IContentRepository --> "many" DXFContent : работает с

IRepositoryFactory -- "0..*" IDocumentRepository : создает
IRepositoryFactory -- "0..*" ILayerRepository : создает
IRepositoryFactory -- "0..*" IEntityRepository : создает
IRepositoryFactory -- "0..*" IContentRepository : создает
IRepositoryFactory -- "0..*" IActiveDocumentRepository : создает

@enduml
```

---

## Описание классов пакета «repositories»

| Интерфейс | Назначение | Тип |
|-----------|-----------|-----|
| **IRepository** | Базовый интерфейс для всех репозиториев. Определяет операции создания, поиска и удаления сущностей. | interface |
| **IDocumentRepository** | Репозиторий для работы с документами DXF (таблица files). Сохранение и извлечение данных документов. | interface |
| **ILayerRepository** | Репозиторий для работы со слоями (таблица layers). Управление слоями в БД. | interface |
| **IEntityRepository** | Репозиторий для работы с элементами (таблица entities). Сохранение геометрии и атрибутов. | interface |
| **IContentRepository** | Репозиторий для хранения бинарного содержимого DXF (таблица contents). | interface |
| **IActiveDocumentRepository** | Репозиторий для активных документов в памяти. Управление открытыми документами. | interface |
| **IConnection** | Интерфейс для подключения к БД. Операции открытия, закрытия, выполнения запросов. | interface |
| **IConnectionFactory** | Factory untuk создание соединений с БД. | interface |
| **IRepositoryFactory** | Factory для создания репозиториев конкретных типов. | interface |

---

## Диаграммы последовательностей взаимодействия объектов

### Нормальный ход событий: Сохранение документа в БД

```uml
@startuml

participant "UseCase" as UseCase
participant "IRepositoryFactory" as Factory
participant "IDocumentRepository" as DocRepo
participant "ILayerRepository" as LayerRepo
participant "IEntityRepository" as EntityRepo
participant "PostgreSQL" as DB

-> UseCase: save(document)
activate UseCase

UseCase -> Factory: get_instance()
activate Factory
Factory --> UseCase: instance
deactivate Factory

UseCase -> DocRepo: save_document(document)
activate DocRepo

DocRepo -> DB: INSERT INTO files (id, filename)
activate DB
DB --> DocRepo: success
deactivate DB

loop для каждого слоя в документе
  UseCase -> LayerRepo: save_layer(layer)
  activate LayerRepo
  
  LayerRepo -> DB: INSERT INTO layers (id, layer_id, name)
  DB --> LayerRepo: success
  deactivate LayerRepo
  
  loop для каждого элемента в слое
    UseCase -> EntityRepo: save_entity(entity)
    activate EntityRepo
    
    EntityRepo -> DB: INSERT INTO entities (id, entity_id, geometry)
    DB --> EntityRepo: success
    deactivate EntityRepo
  end
end

DocRepo --> UseCase: Result[Unit]
deactivate DocRepo

<-- UseCase: Result[Unit]
deactivate UseCase

@enduml
```

### Нормальный ход событий: Поиск документа по ID

```uml
@startuml

participant "Service" as Service
participant "IActiveDocumentRepository" as ActiveRepo
participant "DXFDocument" as Document
participant "In-Memory Cache" as Cache

-> Service: get_by_id(document_id)
activate Service

Service -> ActiveRepo: get_by_id(document_id)
activate ActiveRepo

ActiveRepo -> Cache: lookup(document_id)
activate Cache

alt found in cache
  Cache --> ActiveRepo: DXFDocument
  deactivate Cache
  
  ActiveRepo --> Service: Result[DXFDocument]
  
else not found
  deactivate Cache
  
  ActiveRepo --> Service: Result[None]
end

deactivate ActiveRepo

<-- Service: DXFDocument
deactivate Service

@enduml
```

### Прерывание процесса пользователем: Отмена сохранения

```uml
@startuml

participant "UseCase" as UseCase
participant "IRepositoryFactory" as Factory
participant "IDocumentRepository" as DocRepo
participant "ITransaction" as Transaction
participant "DB" as DB

-> UseCase: save(document)
activate UseCase

UseCase -> Factory: get_instance()
Factory --> UseCase: instance

UseCase -> Transaction: begin()
activate Transaction
Transaction -> DB: BEGIN TRANSACTION
Transaction --> UseCase: started
deactivate Transaction

UseCase -> DocRepo: save_document(document)
activate DocRepo
DocRepo -> DB: INSERT...
DB --> DocRepo: success
deactivate DocRepo

-> UseCase: cancel_save()
activate UseCase

UseCase -> Transaction: rollback()
activate Transaction
Transaction -> DB: ROLLBACK
DB --> Transaction: rolled back
Transaction --> UseCase: success
deactivate Transaction

<-- UseCase: cancelled
deactivate UseCase
deactivate UseCase

@enduml
```

### Прерывание процесса системой: Ошибка подключения БД

```uml
@startuml

participant "UseCase" as UseCase
participant "IDocumentRepository" as DocRepo
participant "IConnection" as Connection
participant "DB" as DB

-> UseCase: save(document)
activate UseCase

UseCase -> DocRepo: save_document(document)
activate DocRepo

DocRepo -> Connection: execute_query(...)
activate Connection

Connection -> DB: send query
DB --> Connection: Connection lost!

Connection --> DocRepo: Exception: ConnectionError
deactivate Connection

DocRepo --> UseCase: Result[fail(error)]
deactivate DocRepo

<-- UseCase: Result[fail(error)]
deactivate UseCase

@enduml
```

---

## Уточненная диаграмма классов (с типами связей)

```uml
@startuml

interface IRepository {
  + save(entity: T): Result[Unit]
  + find_by_id(id: UUID): Result[Optional[T]]
  + delete_by_id(id: UUID): Result[Unit]
  + find_all(): Result[List[T]]
}

interface IDocumentRepository {
  + save_document(doc: DXFDocument): Result[Unit]
  + find_document(id: UUID): Result[Optional[DXFDocument]]
  + update_document(doc: DXFDocument): Result[Unit]
  + find_all_documents(): Result[List[DXFDocument]]
  + delete_document(id: UUID): Result[Unit]
  + find_by_filename(filename: str): Result[Optional[DXFDocument]]
}

interface ILayerRepository {
  + save_layer(layer: DXFLayer): Result[Unit]
  + find_layer(id: UUID): Result[Optional[DXFLayer]]
  + find_layers_by_document(doc_id: UUID): Result[List[DXFLayer]]
  + delete_layer(layer_id: UUID): Result[Unit]
}

interface IEntityRepository {
  + save_entity(entity: DXFEntity): Result[Unit]
  + find_entity(id: UUID): Result[Optional[DXFEntity]]
  + find_entities_by_layer(layer_id: UUID): Result[List[DXFEntity]]
  + delete_entity(entity_id: UUID): Result[Unit]
  + find_by_type(entity_type: DxfEntityType): Result[List[DXFEntity]]
}

interface IContentRepository {
  + save_content(content: DXFContent): Result[Unit]
  + find_content(doc_id: UUID): Result[Optional[DXFContent]]
  + delete_content(content_id: UUID): Result[Unit]
}

interface IActiveDocumentRepository {
  + get_all(): Result[List[DXFDocument]]
  + get_by_id(id: UUID): Result[Optional[DXFBase]]
  + get_by_filename(filename: str): Result[Optional[DXFDocument]]
  + add_active_document(doc: DXFDocument): Result[Unit]
  + remove_active_document(doc_id: UUID): Result[Unit]
  + update_active_document(doc: DXFDocument): Result[Unit]
}

interface IConnection {
  + open(): Result[Unit]
  + close(): Result[Unit]
  + is_connected(): bool
  + execute_query(query: str, params: dict = None): Result[Any]
  + begin_transaction(): Result[Unit]
  + commit(): Result[Unit]
  + rollback(): Result[Unit]
}

interface IConnectionFactory {
  + create_connection(config: ConnectionConfig): Result[IConnection]
}

interface IRepositoryFactory {
  + create_document_repository(): IDocumentRepository
  + create_layer_repository(): ILayerRepository
  + create_entity_repository(): IEntityRepository
  + create_content_repository(): IContentRepository
  + create_active_document_repository(): IActiveDocumentRepository
}

IRepository <|-- IDocumentRepository
IRepository <|-- ILayerRepository
IRepository <|-- IEntityRepository
IRepository <|-- IContentRepository

@enduml
```

---

## Детальная диаграмма классов (все поля и методы)

```uml
@startuml

interface IRepository #CCCCCC {
  {abstract} + save(entity: T): Result[Unit]
  {abstract} + find_by_id(id: UUID): Result[Optional[T]]
  {abstract} + delete_by_id(id: UUID): Result[Unit]
  {abstract} + find_all(): Result[List[T]]
}

interface IDocumentRepository #CCCCCC {
  {abstract} + save_document(doc: DXFDocument): Result[Unit]
  {abstract} + find_document(id: UUID): Result[Optional[DXFDocument]]
  {abstract} + update_document(doc: DXFDocument): Result[Unit]
  {abstract} + find_all_documents(): Result[List[DXFDocument]]
  {abstract} + delete_document(id: UUID): Result[Unit]
  {abstract} + find_by_filename(filename: str): Result[Optional[DXFDocument]]
  {abstract} + count_documents(): Result[int]
}

interface ILayerRepository #CCCCCC {
  {abstract} + save_layer(layer: DXFLayer): Result[Unit]
  {abstract} + find_layer(id: UUID): Result[Optional[DXFLayer]]
  {abstract} + find_layers_by_document(doc_id: UUID): Result[List[DXFLayer]]
  {abstract} + delete_layer(layer_id: UUID): Result[Unit]
  {abstract} + count_layers(doc_id: UUID): Result[int]
}

interface IEntityRepository #CCCCCC {
  {abstract} + save_entity(entity: DXFEntity): Result[Unit]
  {abstract} + find_entity(id: UUID): Result[Optional[DXFEntity]]
  {abstract} + find_entities_by_layer(layer_id: UUID): Result[List[DXFEntity]]
  {abstract} + delete_entity(entity_id: UUID): Result[Unit]
  {abstract} + find_by_type(entity_type: DxfEntityType): Result[List[DXFEntity]]
  {abstract} + count_entities(layer_id: UUID): Result[int]
}

interface IContentRepository #CCCCCC {
  {abstract} + save_content(content: DXFContent): Result[Unit]
  {abstract} + find_content(doc_id: UUID): Result[Optional[DXFContent]]
  {abstract} + delete_content(content_id: UUID): Result[Unit]
}

interface IActiveDocumentRepository #CCCCCC {
  {abstract} + get_all(): Result[List[DXFDocument]]
  {abstract} + get_by_id(id: UUID): Result[Optional[DXFBase]]
  {abstract} + get_by_filename(filename: str): Result[Optional[DXFDocument]]
  {abstract} + add_active_document(doc: DXFDocument): Result[Unit]
  {abstract} + remove_active_document(doc_id: UUID): Result[Unit]
  {abstract} + update_active_document(doc: DXFDocument): Result[Unit]
  {abstract} + clear_all(): Result[Unit]
}

interface IConnection #CCCCCC {
  {abstract} + open(): Result[Unit]
  {abstract} + close(): Result[Unit]
  {abstract} + is_connected(): bool
  {abstract} + execute_query(query: str, params: dict = None): Result[Any]
  {abstract} + begin_transaction(): Result[Unit]
  {abstract} + commit(): Result[Unit]
  {abstract} + rollback(): Result[Unit]
}

interface IConnectionFactory #CCCCCC {
  {abstract} + create_connection(config: ConnectionConfig): Result[IConnection]
}

interface IRepositoryFactory #CCCCCC {
  {abstract} + create_document_repository(): IDocumentRepository
  {abstract} + create_layer_repository(): ILayerRepository
  {abstract} + create_entity_repository(): IEntityRepository
  {abstract} + create_content_repository(): IContentRepository
  {abstract} + create_active_document_repository(): IActiveDocumentRepository
}

IRepository <|-- IDocumentRepository
IRepository <|-- ILayerRepository
IRepository <|-- IEntityRepository
IRepository <|-- IContentRepository

@enduml
```

---

## Описание методов интерфейса «IRepository»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **save** | entity: T | Result[Unit] | Сохраняет или обновляет сущность в хранилище |
| **find_by_id** | id: UUID | Result[Optional[T]] | Находит сущность по уникальному идентификатору |
| **delete_by_id** | id: UUID | Result[Unit] | Удаляет сущность по UUID |
| **find_all** | - | Result[List[T]] | Получает все сущности из хранилища |

---

## Описание методов интерфейса «IDocumentRepository»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **save_document** | doc: DXFDocument | Result[Unit] | Сохраняет документ в таблицу files БД |
| **find_document** | id: UUID | Result[Optional[DXFDocument]] | Находит документ по UUID |
| **update_document** | doc: DXFDocument | Result[Unit] | Обновляет существующий документ |
| **find_all_documents** | - | Result[List[DXFDocument]] | Получает все документы из БД |
| **delete_document** | id: UUID | Result[Unit] | Удаляет документ из БД |
| **find_by_filename** | filename: str | Result[Optional[DXFDocument]] | Находит документ по имени файла |
| **count_documents** | - | Result[int] | Возвращает количество документов |

---

## Описание методов интерфейса «ILayerRepository»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **save_layer** | layer: DXFLayer | Result[Unit] | Сохраняет слой в таблицу layers БД |
| **find_layer** | id: UUID | Result[Optional[DXFLayer]] | Находит слой по UUID |
| **find_layers_by_document** | doc_id: UUID | Result[List[DXFLayer]] | Получает все слои документа |
| **delete_layer** | layer_id: UUID | Result[Unit] | Удаляет слой из БД |
| **count_layers** | doc_id: UUID | Result[int] | Возвращает количество слоев в документе |

---

## Описание методов интерфейса «IEntityRepository»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **save_entity** | entity: DXFEntity | Result[Unit] | Сохраняет элемент в таблицу entities БД |
| **find_entity** | id: UUID | Result[Optional[DXFEntity]] | Находит элемент по UUID |
| **find_entities_by_layer** | layer_id: UUID | Result[List[DXFEntity]] | Получает все элементы слоя |
| **delete_entity** | entity_id: UUID | Result[Unit] | Удаляет элемент из БД |
| **find_by_type** | entity_type: DxfEntityType | Result[List[DXFEntity]] | Находит элементы по типу |
| **count_entities** | layer_id: UUID | Result[int] | Возвращает количество элементов в слое |

---

## Описание методов интерфейса «IActiveDocumentRepository»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **get_all** | - | Result[List[DXFDocument]] | Получает все активные документы (из памяти) |
| **get_by_id** | id: UUID | Result[Optional[DXFBase]] | Получает сущность из активных документов |
| **get_by_filename** | filename: str | Result[Optional[DXFDocument]] | Находит активный документ по имени файла |
| **add_active_document** | doc: DXFDocument | Result[Unit] | Добавляет документ в активные |
| **remove_active_document** | doc_id: UUID | Result[Unit] | Удаляет документ из активных |
| **update_active_document** | doc: DXFDocument | Result[Unit] | Обновляет активный документ |
| **clear_all** | - | Result[Unit] | Очищает все активные документы |

---

## Описание методов интерфейса «IConnectionFactory»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **create_connection** | config: ConnectionConfig | Result[IConnection] | Создает новое соединение с БД по конфигу |

---

## Описание методов интерфейса «IRepositoryFactory»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **create_document_repository** | - | IDocumentRepository | Создает репозиторий документов |
| **create_layer_repository** | - | ILayerRepository | Создает репозиторий слоев |
| **create_entity_repository** | - | IEntityRepository | Создает репозиторий элементов |
| **create_content_repository** | - | IContentRepository | Создает репозиторий содержимого |
| **create_active_document_repository** | - | IActiveDocumentRepository | Создает репозиторий активных документов |

---

## Заключение

Пакет **repositories** определяет контракты для всех операций с данными через систему интерфейсов. Использование Factory паттернов позволяет создавать конкретные реализации для PostgreSQL/PostGIS в слое Infrastructure без нарушения Domain-driven Design. IActiveDocumentRepository управляет документами в памяти, обеспечивая быстрый доступ к открытым файлам.
