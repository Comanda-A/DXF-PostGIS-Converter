# Проектирование пакета application/use_cases

## Исходная диаграмма классов пакета «use_cases»

```uml
@startuml

interface IUseCase {
  + execute(): Result
}

class OpenDocumentUseCase {
  - active_repo: IActiveDocumentRepository
  - dxf_reader: IDXFReader
  - logger: ILogger
  
  + execute(filepath: str): Result[DXFDocument]
}

class ImportUseCase {
  - active_repo: IActiveDocumentRepository
  - logger: ILogger
  - db_session: DBSession
  
  + execute(connection: ConnectionConfigDTO, configs: List[ImportConfigDTO]): Result[Unit]
}

class ExportUseCase {
  - logger: ILogger
  - db_session: DBSession
  - dxf_writer: IDXFWriter
  
  + execute(connection: ConnectionConfigDTO, configs: List[ExportConfigDTO]): Result[Unit]
}

class SelectEntityUseCase {
  - active_repo: IActiveDocumentRepository
  - logger: ILogger
  
  + execute(entity_id: UUID): Result[DXFEntity]
}

class SelectAreaUseCase {
  - active_repo: IActiveDocumentRepository
  - area_selector: IAreaSelector
  - logger: ILogger
  
  + execute(document_id: UUID, params: AreaSelectionParams): Result[List[DXFEntity]]
}

class CloseDocumentUseCase {
  - active_repo: IActiveDocumentRepository
  - logger: ILogger
  
  + execute(document_id: UUID): Result[Unit]
}

class DataViewerUseCase {
  - active_repo: IActiveDocumentRepository
  - logger: ILogger
  
  + execute(document_id: UUID): Result[DXFDocument]
}

IUseCase <|.. OpenDocumentUseCase : реализует
IUseCase <|.. ImportUseCase : реализует
IUseCase <|.. ExportUseCase : реализует
IUseCase <|.. SelectEntityUseCase : реализует
IUseCase <|.. SelectAreaUseCase : реализует
IUseCase <|.. CloseDocumentUseCase : реализует
IUseCase <|.. DataViewerUseCase : реализует

@enduml
```

---

## Описание классов пакета «use_cases»

| Класс | Назначение | Тип |
|-------|-----------|-----|
| **OpenDocumentUseCase** | Открытие DXF файла: чтение из файловой системы, создание сущностей, сохранение в активные документы. | use case |
| **ImportUseCase** | Импорт DXF файла в БД: чтение файла, трансформация в структуру DbGIS, вставка в PostgreSQL/PostGIS. | use case |
| **ExportUseCase** | Экспорт DXF из БД в файл: чтение данных из PostgreSQL/PostGIS, трансформация, запись в .dxf файл. | use case |
| **SelectEntityUseCase** | Выбор отдельного элемента: поиск по UUID, выделение, возврат DTO. | use case |
| **SelectAreaUseCase** | Выбор элементов по площади: применение селектора по координатам, выделение найденных. | use case |
| **CloseDocumentUseCase** | Закрытие документа: удаление из активных, освобождение ресурсов. | use case |
| **DataViewerUseCase** | Просмотр данных документа: получение полной иерархии для отображения. | use case |

---

## Диаграммы последовательностей взаимодействия объектов

### Нормальный ход событий: Открытие документа

```uml
@startuml

participant "User" as User
participant "OpenDocumentUseCase" as UseCase
participant "IDXFReader" as Reader
participant "IActiveDocumentRepository" as Repository
participant "DXFDocument" as Document

-> UseCase: execute(filepath)
activate UseCase

UseCase -> Reader: open(filepath)
activate Reader
Reader --> UseCase: Result[DXFDocument]
deactivate Reader

alt success
  UseCase -> Document: validate()
  activate Document
  Document --> UseCase: true
  deactivate Document
  
  UseCase -> Repository: save(document)
  activate Repository
  Repository --> UseCase: Result[Unit]
  deactivate Repository
  
  <-- UseCase: Result[DXFDocument]
else error
  <-- UseCase: Result.fail(error)
end

deactivate UseCase

@enduml
```

### Нормальный ход событий: Импорт в БД

```uml
@startuml

participant "User" as User
participant "ImportUseCase" as UseCase
participant "DBSession" as Session
participant "IDXFReader" as Reader
participant "IActiveDocumentRepository" as Repository
participant "PostgreSQL" as DB

-> UseCase: execute(connection, configs)
activate UseCase

UseCase -> Session: connect(connection)
activate Session
Session -> DB: CREATE CONNECTION
Session --> UseCase: Result[Unit]
deactivate Session

loop для каждого файла в configs
  UseCase -> Reader: open(filepath)
  activate Reader
  Reader --> UseCase: Result[DXFDocument]
  deactivate Reader
  
  alt success
    UseCase -> Repository: save(document)
    activate Repository
    Repository -> DB: INSERT entities
    DB --> Repository: success
    Repository --> UseCase: Result[Unit]
    deactivate Repository
  else error
    UseCase --> UseCase: log error
  end
end

<-- UseCase: Result[Unit]
deactivate UseCase

@enduml
```

### Прерывание процесса пользователем: Отмена импорта

```uml
@startuml

participant "User" as User
participant "ImportUseCase" as UseCase
participant "DBSession" as Session
participant "Reader" as Reader
participant "Repository" as Repository

-> UseCase: execute(connection, configs)
activate UseCase

UseCase -> Session: connect(connection)
activate Session
Session --> UseCase: success
deactivate Session

loop импорт файлов
  UseCase -> Reader: open(filepath)
  activate Reader
  
  -> User: cancel()
  activate User
  
  Reader --> UseCase: cancelled
  deactivate Reader
  
  loop rollback changes
    UseCase -> Repository: delete_imported_data()
    activate Repository
    Repository --> UseCase: success
    deactivate Repository
  end
  
  <-- User: cancelled
  deactivate User
end

<-- UseCase: Result.fail("Import cancelled")
deactivate UseCase

@enduml
```

### Прерывание процесса системой: Ошибка подключения к БД

```uml
@startuml

participant "ImportUseCase" as UseCase
participant "DBSession" as Session
participant "PostgreSQL" as DB

-> UseCase: execute(connection, configs)
activate UseCase

UseCase -> Session: connect(connection)
activate Session

Session -> DB: CONNECT
DB --> Session: ConnectionError
DB --> Session: Exception

Session --> UseCase: Result.fail(error)
deactivate Session

<-- UseCase: Result.fail("Database connection failed")
deactivate UseCase

@enduml
```

---

## Уточненная диаграмма классов (с типами связей)

```uml
@startuml

interface IUseCase #AAAAAA {
  + execute(): Result
}

class OpenDocumentUseCase {
  - active_repo: IActiveDocumentRepository
  - dxf_reader: IDXFReader
  - logger: ILogger
  
  + __init__(active_repo, dxf_reader, logger)
  + execute(filepath: str): Result[DXFDocument]
  - _validate_filepath(filepath: str): bool
  - _create_document(dxf_data): DXFDocument
}

class ImportUseCase {
  - active_repo: IActiveDocumentRepository
  - logger: ILogger
  - db_session: DBSession
  
  + __init__(active_repo, logger, db_session)
  + execute(connection: ConnectionConfigDTO, configs: List[ImportConfigDTO]): Tuple[Result[Unit], str]
  - _validate_connection(connection): bool
  - _import_file(dxf_document): Result[Unit]
  - _generate_report(lines): str
}

class ExportUseCase {
  - logger: ILogger
  - db_session: DBSession
  - dxf_writer: IDXFWriter
  
  + __init__(logger, db_session, dxf_writer)
  + execute(connection: ConnectionConfigDTO, configs: List[ExportConfigDTO]): Tuple[Result[Unit], str]
  - _load_from_database(connection, config): Result[DXFDocument]
  - _write_to_file(document, filepath): Result[Unit]
}

class SelectEntityUseCase {
  - active_repo: IActiveDocumentRepository
  - logger: ILogger
  
  + __init__(active_repo, logger)
  + execute(entity_id: UUID): Result[DXFEntity]
  - _find_entity(entity_id): Optional[DXFEntity]
  - _mark_selected(entity): void
}

class SelectAreaUseCase {
  - active_repo: IActiveDocumentRepository
  - area_selector: IAreaSelector
  - logger: ILogger
  
  + __init__(active_repo, area_selector, logger)
  + execute(document_id: UUID, params: AreaSelectionParams): Result[List[DXFEntity]]
  - _get_document(document_id): Optional[DXFDocument]
  - _select_in_area(document, params): List[DXFEntity]
}

class CloseDocumentUseCase {
  - active_repo: IActiveDocumentRepository
  - logger: ILogger
  
  + __init__(active_repo, logger)
  + execute(document_id: UUID): Result[Unit]
  - _validate_document_exists(id): bool
}

class DataViewerUseCase {
  - active_repo: IActiveDocumentRepository
  - logger: ILogger
  
  + __init__(active_repo, logger)
  + execute(document_id: UUID): Result[DXFDocument]
  - _fetch_document(id): Optional[DXFDocument]
}

IUseCase <|.. OpenDocumentUseCase
IUseCase <|.. ImportUseCase
IUseCase <|.. ExportUseCase
IUseCase <|.. SelectEntityUseCase
IUseCase <|.. SelectAreaUseCase
IUseCase <|.. CloseDocumentUseCase
IUseCase <|.. DataViewerUseCase

OpenDocumentUseCase -- "1" DXFDocument : зависимость (создает)
ImportUseCase -- "1" DBSession : зависимость (использует)
ExportUseCase -- "1" DBSession : зависимость (использует)

@enduml
```

---

## Детальная диаграмма классов (все поля и методы)

```uml
@startuml

class OpenDocumentUseCase {
  - active_repo: IActiveDocumentRepository
  - dxf_reader: IDXFReader
  - logger: ILogger
  
  + __init__(active_repo: IActiveDocumentRepository,\ndxf_reader: IDXFReader, logger: ILogger)
  + execute(filepath: str) : Result[DXFDocument]
  - _validate_filepath(filepath: str) : bool
  - _load_file(filepath: str) : Result[DXFDocument]
  - _save_to_repository(document: DXFDocument) : Result[Unit]
  - _log_operation(message: str, level: str)
}

class ImportUseCase {
  - active_repo: IActiveDocumentRepository
  - logger: ILogger
  - db_session: DBSession
  - _session: Optional[Session]
  
  + __init__(active_repo: IActiveDocumentRepository,\nlogger: ILogger)
  + execute(connection: ConnectionConfigDTO,\nconfigs: list[ImportConfigDTO])\n: tuple[AppResult[Unit], str]
  - _validate_connection(connection: ConnectionConfigDTO) : bool
  - _validate_configs(configs: list[ImportConfigDTO]) : bool
  - _import_file(filepath: str, config: ImportConfigDTO) : Result[Unit]
  - _convert_and_insert_entities(session: Session,\nentities, layer_class, file_id: int) : bool
  - _apply_field_mapping(entity_data: dict,\nmappings: dict) : dict
  - _generate_report(lines: List[str]) : str
}

class ExportUseCase {
  - logger: ILogger
  - db_session: DBSession
  - dxf_writer: IDXFWriter
  
  + __init__(logger: ILogger)
  + execute(connection: ConnectionConfigDTO,\nconfigs: list[ExportConfigDTO])\n: tuple[AppResult[Unit], str]
  - _validate_connection(connection: ConnectionConfigDTO) : bool
  - _validate_configs(configs: list[ExportConfigDTO]) : bool
  - _load_from_database(session: Session,\nconfig: ExportConfigDTO) : Result[DXFDocument]
  - _write_to_file(document: DXFDocument,\nfilepath: str) : Result[Unit]
  - _create_temp_file() : str
  - _cleanup_temp_files()
  - _generate_report(lines: List[str]) : str
}

class SelectEntityUseCase {
  - active_repo: IActiveDocumentRepository
  - logger: ILogger
  
  + __init__(active_repo: IActiveDocumentRepository,\nlogger: ILogger)
  + execute(entity_id: UUID) : Result[DXFEntity]
  - _find_entity(entity_id: UUID) : Optional[DXFEntity]
  - _mark_as_selected(entity: DXFEntity) : void
  - _save_changes() : Result[Unit]
}

class SelectAreaUseCase {
  - active_repo: IActiveDocumentRepository
  - area_selector: IAreaSelector
  - logger: ILogger
  
  + __init__(active_repo: IActiveDocumentRepository,\narea_selector: IAreaSelector, logger: ILogger)
  + execute(document_id: UUID,\nparams: AreaSelectionParams) : Result[List[DXFEntity]]
  - _get_document(document_id: UUID) : Optional[DXFDocument]
  - _select_in_area(document: DXFDocument,\nparams: AreaSelectionParams) : List[DXFEntity]
  - _mark_selected_entities(entities: List[DXFEntity]) : void
  - _save_changes() : Result[Unit]
}

class CloseDocumentUseCase {
  - active_repo: IActiveDocumentRepository
  - logger: ILogger
  
  + __init__(active_repo: IActiveDocumentRepository,\nlogger: ILogger)
  + execute(document_id: UUID) : Result[Unit]
  - _validate_document_exists(document_id: UUID) : bool
  - _remove_document(document_id: UUID) : Result[Unit]
  - _cleanup_resources(document: DXFDocument) : void
}

class DataViewerUseCase {
  - active_repo: IActiveDocumentRepository
  - logger: ILogger
  
  + __init__(active_repo: IActiveDocumentRepository,\nlogger: ILogger)
  + execute(document_id: UUID) : Result[DXFDocument]
  - _fetch_document(document_id: UUID) : Optional[DXFDocument]
  - _enrich_document_data(document: DXFDocument) : DXFDocument
}

@enduml
```

---

## Описание методов класса «OpenDocumentUseCase»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | active_repo: IActiveDocumentRepository, dxf_reader: IDXFReader, logger: ILogger | None | Инициализирует use case с зависимостями |
| **execute** | filepath: str | Result[DXFDocument] | Открывает DXF файл и сохраняет в активные документы |
| **_validate_filepath** | filepath: str | bool | Проверяет существование файла и право доступа |
| **_load_file** | filepath: str | Result[DXFDocument] | Загружает файл через IDXFReader |
| **_save_to_repository** | document: DXFDocument | Result[Unit] | Сохраняет документ в репозиторий |
| **_log_operation** | message: str, level: str | None | Логирует операцию через ILogger |

---

## Описание методов класса «ImportUseCase»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | active_repo: IActiveDocumentRepository, logger: ILogger | None | Инициализирует use case |
| **execute** | connection: ConnectionConfigDTO, configs: list[ImportConfigDTO] | tuple[AppResult[Unit], str] | Главный метод импорта с отчетом |
| **_validate_connection** | connection: ConnectionConfigDTO | bool | Проверяет корректность конфига БД |
| **_validate_configs** | configs: list[ImportConfigDTO] | bool | Проверяет конфиги импорта |
| **_import_file** | filepath: str, config: ImportConfigDTO | Result[Unit] | Импортирует один DXF файл в БД |
| **_convert_and_insert_entities** | session: Session, entities, layer_class, file_id: int | bool | Конвертирует и вставляет сущности в БД |
| **_apply_field_mapping** | entity_data: dict, mappings: dict | dict | Применяет маппинг полей к данным |
| **_generate_report** | lines: List[str] | str | Генерирует текстовый отчет операции |

---

## Описание методов класса «ExportUseCase»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | logger: ILogger | None | Инициализирует use case |
| **execute** | connection: ConnectionConfigDTO, configs: list[ExportConfigDTO] | tuple[AppResult[Unit], str] | Главный метод экспорта с отчетом |
| **_validate_connection** | connection: ConnectionConfigDTO | bool | Проверяет конфиг подключения БД |
| **_validate_configs** | configs: list[ExportConfigDTO] | bool | Проверяет конфиги экспорта |
| **_load_from_database** | session: Session, config: ExportConfigDTO | Result[DXFDocument] | Загружает данные из PostgreSQL в DXFDocument |
| **_write_to_file** | document: DXFDocument, filepath: str | Result[Unit] | Пишет DXFDocument в .dxf файл |
| **_create_temp_file** | - | str | Создает временный файл |
| **_cleanup_temp_files** | - | None | Удаляет временные файлы |
| **_generate_report** | lines: List[str] | str | Генерирует отчет |

---

## Описание методов класса «SelectEntityUseCase»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | active_repo: IActiveDocumentRepository, logger: ILogger | None | Инициализирует use case |
| **execute** | entity_id: UUID | Result[DXFEntity] | Выбирает отдельный элемент по UUID |
| **_find_entity** | entity_id: UUID | Optional[DXFEntity] | Поиск элемента в активных документах |
| **_mark_as_selected** | entity: DXFEntity | None | Помечает элемент как выбранный |
| **_save_changes** | - | Result[Unit] | Сохраняет изменения в репозиторий |

---

## Описание методов класса «SelectAreaUseCase»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | active_repo: IActiveDocumentRepository, area_selector: IAreaSelector, logger: ILogger | None | Инициализирует use case |
| **execute** | document_id: UUID, params: AreaSelectionParams | Result[List[DXFEntity]] | Главный метод выбора элементов по площади |
| **_get_document** | document_id: UUID | Optional[DXFDocument] | Получает документ по UUID |
| **_select_in_area** | document: DXFDocument, params: AreaSelectionParams | List[DXFEntity] | Выполняет поиск элементов в площади |
| **_mark_selected_entities** | entities: List[DXFEntity] | None | Помечает найденные элементы как выбранные |
| **_save_changes** | - | Result[Unit] | Сохраняет изменения |

---

## Описание методов класса «ExportUseCase»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | active_repo: IActiveDocumentRepository, logger: ILogger | None | Инициализирует use case |
| **execute** | document_id: UUID | Result[Unit] | Закрывает документ и освобождает ресурсы |
| **_validate_document_exists** | document_id: UUID | bool | Проверяет наличие документа |
| **_remove_document** | document_id: UUID | Result[Unit] | Удаляет документ из активных |
| **_cleanup_resources** | document: DXFDocument | None | Освобождает ресурсы (кэш, файлы) |

---

## Описание методов класса «DataViewerUseCase»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | active_repo: IActiveDocumentRepository, logger: ILogger | None | Инициализирует use case |
| **execute** | document_id: UUID | Result[DXFDocument] | Получает документ для просмотра данных |
| **_fetch_document** | document_id: UUID | Optional[DXFDocument] | Загружает документ из репозитория |
| **_enrich_document_data** | document: DXFDocument | DXFDocument | Обогащает документ дополнительными данными для отображения |

---

## Заключение

Пакет **use_cases** реализует все основные бизнес-процессы приложения через паттерн UseCase. Каждый use case инкапсулирует один сценарий использования, обеспечивая высокий уровень абстракции и легкость тестирования. Зависимости на интерфейсы (фреймворки, репозитории, сервисы) позволяют поддерживать Clean Architecture и принцип Dependency Inversion.
