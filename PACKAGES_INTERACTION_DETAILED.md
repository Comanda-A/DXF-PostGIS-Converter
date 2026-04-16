# Взаимодействие пакетов DXF-PostGIS Converter

Полное описание зависимостей и взаимодействия между всеми пакетами приложения.

---

## 1. Структура архитектуры

### 1.1 Domain Layer (src/domain/)
Содержит бизнес-логику и сущности предметной области:

| Пакет | Файлы | Назначение |
|-------|-------|-----------|
| **entities** | dxf_base.py, dxf_document.py, dxf_layer.py, dxf_entity.py, dxf_content.py | Основные сущности DXF (документы, слои, элементы) |
| **repositories** | i_*.py | Интерфейсы для доступа к данным (абстракции) |
| **services** | i_dxf_reader.py, i_dxf_writer.py, i_area_selector.py | Интерфейсы доменных сервисов |
| **value_objects** | result.py, connection_config.py, dxf_entity_type.py, area_selection.py | Неизменяемые объекты значений |

### 1.2 Application Layer (src/application/)
Бизнес-logic операции и orchestration:

| Пакет | Файлы | Назначение |
|-------|-------|-----------|
| **use_cases** | *_use_case.py | Варианты использования (Import, Export, Open, etc.) |
| **services** | active_document_service.py, connection_config_service.py | Прикладные сервисы управления |
| **mappers** | dxf_mapper.py | Преобразование Entity → DTO |
| **dtos** | *_dto.py | Data Transfer Objects для передачи данных |
| **events** | i_event.py, i_app_events.py | Интерфейсы событий приложения |
| **interfaces** | i_logger.py, i_localization.py, i_settings.py | Интерфейсы сервисов инфраструктуры |
| **results** | app_result.py | Результат выполнения операций |
| **database** | db_session.py | Сессия БД |

### 1.3 Presentation Layer (src/presentation/)
UI и взаимодействие с пользователем:

| Пакет | Файлы | Назначение |
|-------|-------|-----------|
| **dialogs** | *_dialog.py | Qt диалоги (основной интерфейс) |
| **widgets** | *_handler.py | Qt виджеты и компоненты UI |
| **workers** | long_task_worker.py | Фоновые потоки для долгих операций |
| **services** | dialog_translator.py, area_selection_controller.py | Сервисы для dialogs |

### 1.4 Infrastructure Layer (src/infrastructure/)
Реализация интерфейсов и технические детали:

| Пакет | Файлы | Назначение |
|-------|-------|-----------|
| **database** | active_document_repository.py, connection_factory.py, repository_factory.py, postgis/ | PostgreSQL/PostGIS хранилище |
| **ezdxf** | dxf_reader.py, dxf_writer.py, area_selector.py | Реализация DXF операций (чтение/запись) |
| **qgis** | logger.py, qt_app_events.py, qt_event.py, settings.py | Qt/QGIS интеграция |
| **localization** | localization.py | Локализация интерфейса |

---

## 2. Граф зависимостей по слоям

```mermaid
graph TB
    subgraph Domain["🟦 DOMAIN LAYER"]
        entities["📦 entities<br/>(DXFBase, DXFDocument,<br/>DXFLayer, DXFEntity,<br/>DXFContent)"]
        repositories["📦 repositories<br/>(IRepository,<br/>IDocumentRepository,<br/>ILayerRepository, etc.)"]
        services_domain["📦 services<br/>(IDXFReader,<br/>IDXFWriter,<br/>IAreaSelector)"]
        value_objects["📦 value_objects<br/>(Result, ConnectionConfig,<br/>DxfEntityType)"]
        
        entities ---|uses| value_objects
        services_domain ---|depends on| entities
        repositories ---|depends on| entities
    end
    
    subgraph Application["🟩 APPLICATION LAYER"]
        use_cases["📦 use_cases<br/>(ImportUseCase,<br/>ExportUseCase, etc.)"]
        app_services["📦 services<br/>(ActiveDocumentService,<br/>ConnectionConfigService)"]
        mappers["📦 mappers<br/>(DXFMapper)"]
        dtos["📦 dtos<br/>(*DTO, ImportMode,<br/>ExportMode)"]
        events["📦 events<br/>(IEvent,<br/>IAppEvents)"]
        interfaces["📦 interfaces<br/>(ILogger,<br/>ILocalization,<br/>ISettings)"]
        results["📦 results<br/>(AppResult)"]
        database["📦 database<br/>(DBSession)"]
        
        use_cases -->|uses| app_services
        use_cases -->|uses| dtos
        use_cases -->|uses| repositories
        use_cases -->|uses| results
        app_services -->|uses| entities
        app_services -->|uses| dtos
        app_services -->|uses| repositories
        mappers -->|transforms| entities
        mappers -->|creates| dtos
        events ---|depends on| value_objects
        database ---|uses| interfaces
    end
    
    subgraph Presentation["🟨 PRESENTATION LAYER"]
        dialogs["📦 dialogs<br/>(ConverterDialog,<br/>ImportDialog, etc.)"]
        widgets["📦 widgets<br/>(DXFTreeHandler,<br/>QGISLayerSyncManager)"]
        workers["📦 workers<br/>(LongTaskWorker)"]
        pres_services["📦 services<br/>(DialogTranslator,<br/>AreaSelectionController)"]
        
        dialogs -->|uses| use_cases
        dialogs -->|uses| app_services
        dialogs -->|uses| dtos
        dialogs -->|uses| widgets
        dialogs -->|uses| workers
        dialogs -->|uses| pres_services
        dialogs -->|uses| events
        dialogs -->|uses| interfaces
        widgets -->|communicates with| dialogs
        workers -->|executes| use_cases
        pres_services -->|supports| dialogs
    end
    
    subgraph Infrastructure["🟪 INFRASTRUCTURE LAYER"]
        db["📦 database<br/>(PostgreSQL/PostGIS<br/>Repositories)"]
        ezdxf_impl["📦 ezdxf<br/>(DXFFileReader,<br/>DXFFileWriter,<br/>AreaSelectorImpl)"]
        qgis_impl["📦 qgis<br/>(QtLogger,<br/>QtAppEvents,<br/>QtSettings)"]
        localization["📦 localization<br/>(LocalizationManager)"]
        
        db ---|implements| repositories
        db ---|uses| value_objects
        ezdxf_impl ---|implements| services_domain
        ezdxf_impl ---|creates| entities
        qgis_impl ---|implements| interfaces
        qgis_impl ---|publishes| events
        localization ---|implements| interfaces
    end
    
    Presentation -->|depends on| Application
    Application -->|depends on| Domain
    Infrastructure -->|implements| Application
    Infrastructure -->|implements| Domain
```

---

## 3. Взаимодействие пакетов в рамках слоев

### 3.1 DOMAIN LAYER

#### 3.1.1 entities ↔ repositories
**Направление:** Repositories работают с Entities

```
repositories (interfaces)
    ↓
    содержат методы для работы с:
    ├── IDocumentRepository.save(DXFDocument)
    ├── ILayerRepository.save(DXFLayer)
    ├── IEntityRepository.save(DXFEntity)
    └── IActiveDocumentRepository.get_all() → List[DXFDocument]

entities
    ↑
    используются как типы параметров и возвращаемых значений
```

#### 3.1.2 entities ↔ services (domain)
**Направление:** Domain Services работают с Entities

```
Entity Flow:
IDXFReader
    ├── open(filepath) → Result[DXFDocument]
    │   ↓
    │   Создает иерархию:
    │   DXFDocument
    │   ├── DXFContent (bytes)
    │   ├── DXFLayer (список)
    │   │   └── DXFEntity (список)
    │   └── DXFLayer...

IDXFWriter
    ├── save(DXFDocument, filepath) → Result[Unit]
    │   ↑
    │   Использует иерархию DXFDocument
    │   для сохранения в файл

IAreaSelector
    └── select(DXFDocument, params) → List[DXFEntity]
        ↑
        Работает с сущностями в документе
```

#### 3.1.3 value_objects использование
```
value_objects используются везде:
- Result[T]          → Обертка для результатов операций
- ConnectionConfig   → Конфиг подключения БД
- DxfEntityType      → Тип элемента DXF
- AreaSelectionParams → Параметры выбора по площади
- Unit              → Пустой результат
```

---

### 3.2 APPLICATION LAYER

#### 3.2.1 Зависимости entities + repositories
```
use_cases
    ↓
    import_use_case.py:
    ├── self._active_repo: IActiveDocumentRepository
    │   └── repo.get_all() → Result[List[DXFDocument]]
    ├── repo.save(DXFDocument)
    ├── repo.save(DXFLayer)
    └── repo.save(DXFEntity)
```

#### 3.2.2 dtos ↔ mappers
**Направление:** Mappers преобразуют Entities в DTOs

```
DXFMapper.to_dto(DXFBase) → DXFBaseDTO
├── DXFDocument → DXFDocumentDTO
├── DXFLayer → DXFLayerDTO
├── DXFEntity → DXFEntityDTO
└── DXFContent → (как часть в DTO)

Примечание: Маппер выполняет рекурсивное преобразование
иерархии объектов
```

#### 3.2.3 use_cases ↔ services (application)
```
use_cases
    ├── export_use_case --> DBSession (database)
    ├── import_use_case --> ActiveDocumentService
    ├── open_document_use_case --> IDXFReader (domain service)
    ├── select_entity_use_case --> ActiveDocumentService
    └── select_area_use_case --> IAreaSelector (domain service)

app_services
    ├── ActiveDocumentService
    │   ├── uses IActiveDocumentRepository
    │   ├── uses DXFMapper
    │   └── returns DTO objects
    └── ConnectionConfigService
        └── works with ConnectionConfigDTO
```

#### 3.2.4 events ↔ interfaces
```
events (interfaces)
    ├── IEvent[T]
    └── IAppEvents
        └── published by infrastructure/qgis

interfaces (for infrastructure)
    ├── ILogger (implemented in infrastructure/qgis)
    ├── ILocalization (implemented in infrastructure/localization)
    └── ISettings (implemented in infrastructure/qgis)
```

#### 3.2.5 results использование
```
AppResult[T]
    используется как возвращаемый тип во всех use_cases:
    ├── import_use_case → AppResult[Unit]
    ├── export_use_case → AppResult[Unit]
    ├── open_document_use_case → AppResult[DXFDocument]
    └── и т.д.
```

---

### 3.3 PRESENTATION LAYER

#### 3.3.1 dialogs (главная точка интеграции)
```
ConverterDialog (главный диалог)
    ├── @inject use_cases
    │   ├── OpenDocumentUseCase
    │   ├── ImportUseCase
    │   ├── ExportUseCase
    │   ├── SelectEntityUseCase
    │   └── SelectAreaUseCase
    ├── @inject app_services
    │   └── ActiveDocumentService
    ├── @inject interfaces
    │   ├── ILocalization
    │   ├── ILogger
    │   └── ISettings
    ├── @inject events
    │   └── IAppEvents
    ├── uses widgets
    │   └── SelectableDxfTreeHandler
    ├── uses workers
    │   └── LongTaskWorker
    └── uses presentation/services
        ├── DialogTranslator
        └── AreaSelectionController
```

#### 3.3.2 widgets ↔ dialogs
```
Widgets (UI компоненты):
    ├── SelectableDxfTreeHandler
    │   └── управляет древом документов в UI
    ├── ViewerDxfTreeHandler
    │   └── отображает DXF структуру
    ├── QGISLayerSyncManager
    │   └── синхронизирует состояние с QGIS
    └── PreviewComponents
        └── отображает предпросмотр

Взаимодействие:
    dialog → создает widgets
    widgets → генерируют сигналы
    dialog → обрабатывает сигналы → вызывает use_cases
```

#### 3.3.3 workers ↔ use_cases
```
LongTaskWorker (Qt QThread)
    ├── принимает функцию (use_case.execute)
    ├── запускает в отдельном потоке
    ├── emits progress signals
    ├── emits finished signal with result
    └── emits error signal

Использование:
    dialog → создает LongTaskWorker(use_case.execute)
    worker → runs in background
    dialog → обновляет UI по сигналам worker
```

#### 3.3.4 presentation/services
```
DialogTranslator
    └── подддерживает dialogs с локализацией

AreaSelectionController
    ├── управляет выбором по площади
    ├── работает с SelectAreaUseCase
    └── обновляет UI через dialogs
```

---

### 3.4 INFRASTRUCTURE LAYER

#### 3.4.1 database (PostgreSQL/PostGIS)
```
database/
    ├── repository_factory.py
    │   └── создает конкретные репозитории для DB
    ├── connection_factory.py
    │   └── создает соединения с БД
    ├── active_document_repository.py
    │   └── реализует IActiveDocumentRepository
    └── postgis/
        ├── DXF entity repository impl
        ├── Layer repository impl
        └── и т.д.

Реализация interfaces (repositories):
    IDocumentRepository → postgis.DocumentRepository
    ILayerRepository → postgis.LayerRepository
    IEntityRepository → postgis.EntityRepository
    и т.д.
```

#### 3.4.2 ezdxf (DXF file operations)
```
ezdxf/
    ├── dxf_reader.py (реализует IDXFReader)
    │   ├── читает физический DXF файл через ezdxf lib
    │   ├── создает domain entities
    │   └── отправляет Result[DXFDocument]
    ├── dxf_writer.py (реализует IDXFWriter)
    │   ├── получает DXFDocument
    │   ├── пишет физический DXF файл
    │   └── возвращает Result[Unit]
    └── area_selector.py (реализует IAreaSelector)
        ├── выбирает entities по площади
        └── возвращает список DXFEntity

Соединение с domain:
    Implements:
        IDXFReader ← DXFReader
        IDXFWriter ← DXFWriter
        IAreaSelector ← AreaSelector
```

#### 3.4.3 qgis (Qt/QGIS integration)
```
qgis/
    ├── logger.py
    │   └── QtLogger implements ILogger
    ├── qt_app_events.py
    │   └── QtAppEvents implements IAppEvents
    ├── qt_event.py
    │   └── QtEvent implements IEvent
    └── settings.py
        └── QtSettings implements ISettings

Роль:
    ├── Предоставляет конкретные реализации интерфейсов
    ├── Использует Qt для логирования, сигналов
    ├── Интегрирует с QGIS API
    └── Опубликовано events для приложения
```

#### 3.4.4 localization
```
localization/
    └── localization.py
        └── LocalizationManager implements ILocalization
            ├── загружает строки из i18n/ (en.py, ru.py)
            ├── предоставляет методы перевода
            └── поддерживает множественные языки
```

---

## 4. Диаграмма потока данных для ключевых операций

### 4.1 Операция импорта DXF файла

```mermaid
sequenceDiagram
    User->>ConverterDialog: нажимает "Import"
    ConverterDialog->>LongTaskWorker: создает worker для ImportUseCase
    LongTaskWorker->>ImportUseCase: execute(connection, configs)
    ImportUseCase->>OpenDocumentUseCase: execute(filepath)
    OpenDocumentUseCase->>IDXFReader: open(filepath) [domain service]
    Note over IDXFReader: impl: infrastructure/ezdxf/DXFReader
    IDXFReader->>IDXFReader: ezdxf.readfile() - читает физический файл
    IDXFReader->>entities: создает DXFDocument с layers и entities
    IDXFReader-->>OpenDocumentUseCase: Result[DXFDocument]
    OpenDocumentUseCase-->>ImportUseCase: Result[DXFDocument]
    ImportUseCase->>IActiveDocumentRepository: save(DXFDocument)
    Note over IActiveDocumentRepository: impl: infrastructure/database
    IActiveDocumentRepository->>IActiveDocumentRepository: сохраняет в PostgreSQL/PostGIS
    IActiveDocumentRepository-->>ImportUseCase: Result[Unit]
    ImportUseCase-->>LongTaskWorker: Result[Unit]
    LongTaskWorker-->>ConverterDialog: finished signal с результатом
    ConverterDialog->>ConverterDialog: обновляет UI
    ConverterDialog->>ActiveDocumentService: get_all()
    ActiveDocumentService->>IActiveDocumentRepository: get_all()
    IActiveDocumentRepository-->>ActiveDocumentService: List[DXFDocument]
    ActiveDocumentService->>DXFMapper: to_dto(documents)
    DXFMapper-->>ActiveDocumentService: List[DXFDocumentDTO]
    ActiveDocumentService-->>ConverterDialog: List[DXFDocumentDTO]
    ConverterDialog->>SelectableDxfTreeHandler: обновляет tree с DTO
    SelectableDxfTreeHandler-->>User: отображает структуру
```

### 4.2 Операция экспорта DXF в файл

```mermaid
sequenceDiagram
    User->>ConverterDialog: нажимает "Export"
    ConverterDialog->>LongTaskWorker: создает worker для ExportUseCase
    LongTaskWorker->>ExportUseCase: execute(connection, configs)
    ExportUseCase->>DBSession: connect(connection)
    DBSession->>DBSession: подключается к PostgreSQL
    DBSession-->>ExportUseCase: Result[Unit]
    ExportUseCase->>IDocumentRepository: get(document_id) [из БД]
    Note over IDocumentRepository: impl: infrastructure/database
    IDocumentRepository-->>ExportUseCase: DXFDocument
    ExportUseCase->>IDXFWriter: save(document, filepath) [domain service]
    Note over IDXFWriter: impl: infrastructure/ezdxf/DXFWriter
    IDXFWriter->>IDXFWriter: конвертирует DXFDocument в DXF структуру
    IDXFWriter->>IDXFWriter: ezdxf.new() + добавляет entities
    IDXFWriter->>IDXFWriter: пишет в .dxf файл
    IDXFWriter-->>ExportUseCase: Result[Unit]
    ExportUseCase-->>LongTaskWorker: Result[Unit]
    LongTaskWorker-->>ConverterDialog: finished signal
    ConverterDialog->>ConverterDialog: показывает результат
```

### 4.3 Выбор элементов по площади

```mermaid
sequenceDiagram
    User->>SelectableDxfTreeHandler: рисует прямоугольник на карте
    SelectableDxfTreeHandler->>SelectAreaUseCase: execute(document_id, params)
    SelectAreaUseCase->>ActiveDocumentService: _get_by_id(document_id)
    ActiveDocumentService->>IActiveDocumentRepository: get_all()
    IActiveDocumentRepository-->>ActiveDocumentService: List[DXFDocument]
    ActiveDocumentService-->>SelectAreaUseCase: DXFDocument
    SelectAreaUseCase->>IAreaSelector: select(document, params) [domain service]
    Note over IAreaSelector: impl: infrastructure/ezdxf/AreaSelector
    IAreaSelector->>IAreaSelector: анализирует координаты элементов
    IAreaSelector->>IAreaSelector: проверяет пересечение с площадью
    IAreaSelector-->>SelectAreaUseCase: List[DXFEntity]
    SelectAreaUseCase->>SelectAreaUseCase: помечает selected=True
    SelectAreaUseCase->>IActiveDocumentRepository: save(entities)
    IActiveDocumentRepository-->>SelectAreaUseCase: Result[Unit]
    SelectAreaUseCase-->>SelectableDxfTreeHandler: Result[Unit]
    SelectableDxfTreeHandler->>SelectableDxfTreeHandler: обновляет checkboxы в tree
    SelectableDxfTreeHandler->>QGISLayerSyncManager: синхронизирует с QGIS
```

---

## 5. Матрица зависимостей

```mermaid
graph LR
    subgraph D["DOMAIN 🟦"]
        D_ENT["entities"]
        D_REP["repositories"]
        D_SRV["services"]
        D_VO["value_objects"]
    end
    
    subgraph A["APPLICATION 🟩"]
        A_UC["use_cases"]
        A_SRV["services"]
        A_DTO["dtos"]
        A_MAP["mappers"]
        A_EVT["events"]
        A_INT["interfaces"]
        A_RES["results"]
        A_DB["database"]
    end
    
    subgraph P["PRESENTATION 🟨"]
        P_DLG["dialogs"]
        P_WGT["widgets"]
        P_WRK["workers"]
        P_SRV["services"]
    end
    
    subgraph I["INFRASTRUCTURE 🟪"]
        I_DB["database"]
        I_EZD["ezdxf"]
        I_QGS["qgis"]
        I_LOC["localization"]
    end
    
    %% Domain internal
    D_REP -->|works with| D_ENT
    D_SRV -->|works with| D_ENT
    D_ENT -->|uses| D_VO
    
    %% Application uses Domain
    A_UC -->|uses| D_REP
    A_UC -->|uses| D_SRV
    A_SRV -->|uses| D_ENT
    A_DTO -->|related to| D_ENT
    A_MAP -->|transforms| D_ENT
    A_MAP -->|creates| A_DTO
    
    %% Application internal
    A_UC -->|uses| A_SRV
    A_UC -->|uses| A_DTO
    A_UC -->|returns| A_RES
    A_INT -->|used by| A_UC
    A_INT -->|used by| A_DB
    
    %% Presentation uses Application
    P_DLG -->|uses| A_UC
    P_DLG -->|uses| A_SRV
    P_DLG -->|uses| A_DTO
    P_DLG -->|uses| A_INT
    P_DLG -->|uses| A_EVT
    P_DLG -->|manages| P_WGT
    P_DLG -->|owns| P_WRK
    P_DLG -->|uses| P_SRV
    P_WRK -->|executes| A_UC
    
    %% Infrastructure implements Domain & Application
    I_DB -->|implements| D_REP
    I_EZD -->|implements| D_SRV
    I_QGS -->|implements| A_INT
    I_LOC -->|implements| A_INT
    I_QGS -->|publishes| A_EVT
    
    classDef domain fill:#6B9BD1
    classDef app fill:#7CB342
    classDef pres fill:#FFD54F
    classDef infra fill:#AB47BC
    
    class D_ENT,D_REP,D_SRV,D_VO domain
    class A_UC,A_SRV,A_DTO,A_MAP,A_EVT,A_INT,A_RES,A_DB app
    class P_DLG,P_WGT,P_WRK,P_SRV pres
    class I_DB,I_EZD,I_QGS,I_LOC infra
```

---

## 6. Таблица межпакетных взаимодействий

| From | To | Type | Purpose | Data Passed |
|------|----|----|---------|------------|
| **use_cases** | repositories | import | доступ к данным | Entity objects |
| **use_cases** | domain/services | import | бизнес-операции | parameters |
| **use_cases** | dtos | import | результаты | DTO objects |
| **use_cases** | results | import | обертка результатов | Result[T] |
| **use_cases** | database | import | сессия БД | DBSession |
| **app/services** | entities | import | управление | Entity objects |
| **app/services** | dtos | import | преобразование | DTO objects |
| **app/services** | repositories | import | доступ | Entity objects |
| **mappers** | entities | import | трансформация | DXFBase (domain) |
| **mappers** | dtos | import | создание | DXFBaseDTO |
| **dialogs** | use_cases | import | вызов операций | parameters |
| **dialogs** | app/services | import | управление | Entity info |
| **dialogs** | widgets | composition | UI управление | QPySignal |
| **dialogs** | workers | composition | фон. потоки | lambda functions |
| **dialogs** | interfaces | import | сервисы | logger, settings, localization |
| **dialogs** | events | import | подписка | IAppEvents |
| **widgets** | dialogs | reference | обновления UI | signals |
| **workers** | use_cases | execution | фон. работа | execute() |
| **database** | repositories | implementation | PostgreSQL | SQL queries |
| **database** | entities | import | сохранение | Entity objects |
| **ezdxf** | domain/services | implementation | DXF операции | IDXFReader/Writer |
| **ezdxf** | entities | creation | объекты | DXFDocument |
| **qgis** | interfaces | implementation | QGIS интеграция | Qt signals/slots |
| **localization** | interfaces | implementation | i18n | translation strings |

---

## 7. Правила и паттерны

### 7.1 Направление зависимостей (SOLID)
```
✅ ПРАВИЛЬНО:
Presentation → Application → Domain
Presentation → Infrastructure (для интерфейсов)
Application → Domain
Infrastructure → Domain (implements)
Infrastructure → Application (implements)

❌ НЕПРАВИЛЬНО:
Domain → Application (circular)
Domain → Infrastructure (tight coupling)
Domain → Presentation
```

### 7.2 Трансляция данных между слоями
```
Domain entities  →  Mappers  →  Application DTOs
↓                                       ↓
(содержат бизнес-логику)        (структуры для передачи)

Exceptions: entities внутри одного слоя используются напрямую
```

### 7.3 Инъекция зависимостей (inject)
```python
@inject.autoparams(
    'open_doc_use_case',      # use_case
    'active_doc_service',      # app service
    'logger',                   # infrastructure
    'localization'             # infrastructure
)
def __init__(self, ...):
    # Spring-style IoC контейнер
    pass
```

### 7.4 Асинхронные операции
```
Долгие операции (import/export) запускаются в LongTaskWorker:
    · Не блокирует UI
    · Emit signals: progress, finished, error
    · Результат передается в основной поток
```

---

## 8. Ключевые точки интеграции

### 8.1 Граница Domain ↔ Application
```
Domain: entities, repositories, value_objects, domain/services
    ↓ (используются напрямую)
Application: use_cases, app/services
    ↓ (преобразуются в)
Application: dtos
```

### 8.2 Граница Application ↔ Presentation
```
Application: use_cases, app/services, interfaces, events
    ↓ (injected в)
Presentation: dialogs
    ↓ (результаты)
Presentation: dtos via mappers
    ↓ (отображаются в)
Presentation: widgets
```

### 8.3 Граница Infrastructure ↔ Domain/Application
```
Domain/Application: interfaces (IRepository, IDXFReader, ILogger)
    ↑ (реализуются)
Infrastructure: database/, ezdxf/, qgis/, localization/
```

---

## 9. Заключение

Архитектура приложения следует принципам **Clean Architecture** с четким разделением:

✅ **Domain** — чистая бизнес-логика, независимая от фреймворков
✅ **Application** — сценарии использования и оркестрация
✅ **Presentation** — UI, диалоги, виджеты Qt/QGIS
✅ **Infrastructure** — внешние сервисы: БД, DXF файлы, QGIS

Каждый слой имеет ясные границы и зависимости направлены внутрь → архитектура легко тестируется и расширяется.
