# Таблица описания всех модулей

**Полный реестр всех Python модулей в системе**

---

## 1. Основные модули (Entry Points)

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `__init__.py` (root) | Инициализация пакета плагина | Путь пакета | Экспортированные классы |
| `dxf_postgis_converter.py` | Точка входа QGIS плагина | QgsInterface | MainDialog (UI) |
| `container.py` | Контейнер Dependency Injection | Конфигурация | Настроенные сервисы |

---

## 2. Domain Layer - Entities

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `domain/entities/__init__.py` | Экспорт классов сущностей | - | DXFBase, DXFDocument, DXFLayer, DXFEntity |
| `domain/entities/dxf_base.py` | Абстрактный базовый класс для всех DXF объектов | UUID, is_selected | ID, поле выделения |
| `domain/entities/dxf_document.py` | Документ DXF (корневой объект) | Имя учетной записи, изображение | DXFDocument с слоями |
| `domain/entities/dxf_layer.py` | Слой DXF (коллекция сущностей) | Имя слоя, цвет DXF | Слой с геометриями |
| `domain/entities/dxf_entity.py` | Сущность DXF (примитив: LINE, CIRCLE) | Тип, геометрия, стиль | Entity с координатами |
| `domain/entities/dxf_content.py` | Бинарное содержимое DXF | Бинарные данные файла | Содержимое с метаданными |

---

## 3. Domain Layer - Repositories (Interfaces)

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `domain/repositories/__init__.py` | Экспорт интерфейсов репозиториев | - | Интерфейсы IRepository, IConnection, IFactory |
| `domain/repositories/i_connection.py` | Интерфейс подключения к БД | - | Методы connect(), disconnect(), execute_query() |
| `domain/repositories/i_repository.py` | Базовый интерфейс CRUD операций | - | Методы create(), read(), update(), delete() |
| `domain/repositories/i_document_repository.py` | Интерфейс для работы с документами | - | find_by_id(), find_all(), save(), delete() |
| `domain/repositories/i_layer_repository.py` | Интерфейс для работы со слоями | - | find_by_document(), save_layer() |
| `domain/repositories/i_entity_repository.py` | Интерфейс для работы с сущностями | - | find_by_layer(), find_by_type(), save_entity() |
| `domain/repositories/i_content_repository.py` | Интерфейс для работы с бинарным содержимым | - | save_binary(), retrieve_binary() |
| `domain/repositories/i_active_document_repository.py` | Интерфейс для текущего активного документа | - | get_active(), set_active() |
| `domain/repositories/i_connection_factory.py` | Фабрика подключений | Конфиг подключения | IConnection |
| `domain/repositories/i_repository_factory.py` | Фабрика репозиториев | IConnection | Экземпляры репозиториев |

---

## 4. Domain Layer - Services

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `domain/services/__init__.py` | Экспорт доменных сервисов | - | DocumentService, LayerService, EntityService |
| `domain/services/document_service.py` | Бизнес-логика документов | DXFDocument, операции | OperationResult, DXFDocument |
| `domain/services/layer_service.py` | Бизнес-логика слоев | DXFLayer, параметры | DXFLayer, результат |
| `domain/services/entity_service.py` | Бизнес-логика сущностей | DXFEntity, трансформация | DXFEntity с измененными свойствами |
| `domain/services/selection_service.py` | Управление выделением | UUID список, флаги | Список выбранных объектов |

---

## 5. Domain Layer - Value Objects

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `domain/value_objects/__init__.py` | Экспорт value objects | - | Bounds, Color, Point, Geometry, EntityType |
| `domain/value_objects/bounds.py` | Прямоугольник ограничивающий компонент (XMin, XMax, YMin, YMax) | Координаты | Объект Bounds |
| `domain/value_objects/color.py` | Цвет (R, G, B, A) | RGB(A) значения | Color объект |
| `domain/value_objects/point.py` | 2D/3D точка (X, Y, Z) | Координаты | Point объект |
| `domain/value_objects/geometry.py` | WKT геометрия (POINT, LINESTRING, POLYGON) | WKT строка | Geometry объект |
| `domain/value_objects/entity_type.py` | Enum типов сущностей (LINE, CIRCLE, ARC, POLYGON...) | - | EntityType enum |
| `domain/value_objects/operation_result.py` | Результат операции (успех/ошибка) | is_success, message, data | OperationResult |

---

## 6. Application Layer - Use Cases

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `application/use_cases/__init__.py` | Экспорт use case'ов | - | OpenDocumentUseCase, ImportUseCase и т.д. |
| `application/use_cases/open_document_use_case.py` | Открыть DXF документ | Путь к файлу | DXFDocument |
| `application/use_cases/import_use_case.py` | Импортировать DXF в БД | DXFDocument, конфиг | OperationResult, количество записей |
| `application/use_cases/export_use_case.py` | Экспортировать из БД в файл | Параметры фильтра, путь | DXF файл, статус |
| `application/use_cases/select_entity_use_case.py` | Выбрать сущность по ID | Entity ID | Selected Entity |
| `application/use_cases/select_area_use_case.py` | Выбрать сущности в области (XY) | Bounds (XMin, XMax, YMin, YMax) | Список Entity |
| `application/use_cases/close_document_use_case.py` | Закрыть документ | DXFDocument | OperationResult |
| `application/use_cases/data_viewer_use_case.py` | Просмотреть данные в таблице | Параметры фильтра | DataFrame или таблица |

---

## 7. Application Layer - Services

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `application/services/__init__.py` | Экспорт сервисов | - | ActiveDocumentService, ImportService и т.д. |
| `application/services/active_document_service.py` | Управление текущим активным документом | DXFDocument или None | Current document |
| `application/services/import_service.py` | Оркестрирует импорт (валидация, маппинг, сохранение) | DXFDocument, конфиг | OperationResult |
| `application/services/export_service.py` | Оркестрирует экспорт (чтение, трансформирование, запись) | Параметры, путь | OperationResult |
| `application/services/cache_service.py` | Кеширование результатов запросов | Ключ, значение | Кешированное значение |
| `application/services/validation_service.py` | Валидация данных (DXF, конфиги) | Объект для валидации | ValidationResult (ошибки/предупреждения) |

---

## 8. Application Layer - DTOs

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `application/dtos/__init__.py` | Экспорт DTO классов | - | DTO классы |
| `application/dtos/dxf_base_dto.py` | DTO для DXFBase (id, is_selected) | Entity | DTO |
| `application/dtos/dxf_document_dto.py` | DTO для документа (name, account, image) | DXFDocument | DocumentDTO |
| `application/dtos/dxf_layer_dto.py` | DTO для слоя (name, color, entities) | DXFLayer | LayerDTO |
| `application/dtos/dxf_entity_dto.py` | DTO для сущности (type, geometry, style) | DXFEntity | EntityDTO |
| `application/dtos/connection_config_dto.py` | DTO конфига подключения (host, port, database) | Конфиг | ConnectionConfigDTO |
| `application/dtos/import_config_dto.py` | DTO конфига импорта (режим, фильтры) | Конфиг | ImportConfigDTO |
| `application/dtos/export_config_dto.py` | DTO конфига экспорта (режим, формат) | Конфиг | ExportConfigDTO |
| `application/dtos/import_mode.py` | Enum режимов импорта (APPEND, REPLACE, MERGE) | - | ImportMode enum |
| `application/dtos/export_mode.py` | Enum режимов экспорта (FULL, FILTERED, LAYERS) | - | ExportMode enum |

---

## 9. Application Layer - Mappers

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `application/mappers/__init__.py` | Экспорт маппсеров | - | DXFMapper, ConfigMapper |
| `application/mappers/dxf_mapper.py` | Маппер Entity ← → DTO | Entity или DTO | DTO или Entity |
| `application/mappers/connection_config_mapper.py` | Маппер конфига подключения | dict или объект | ConnectionConfigDTO |
| `application/mappers/import_config_mapper.py` | Маппер конфига импорта | dict или объект | ImportConfigDTO |

---

## 10. Application Layer - Events

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `application/events/__init__.py` | Экспорт событий и интерфейсов | - | Event классы, IAppEventBus |
| `application/events/i_app_events.py` | Интерфейс шины событий | - | Методы subscribe(), publish() |
| `application/events/i_event.py` | Базовый интерфейс события | - | Свойства event_type, timestamp |
| `application/events/document_opened_event.py` | Событие открытия документа | DXFDocument | DocumentOpenedEvent |
| `application/events/selection_changed_event.py` | Событие изменения выделения | UUID список | SelectionChangedEvent |
| `application/events/import_completed_event.py` | Событие завершения импорта | OperationResult | ImportCompletedEvent |

---

## 11. Application Layer - Interfaces

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `application/interfaces/__init__.py` | Экспорт интерфейсов | - | ILogger, ILocalization, ISettings |
| `application/interfaces/i_logger.py` | Интерфейс логирования | message, level | Запись в лог |
| `application/interfaces/i_localization.py` | Интерфейс локализации | ключ, язык | Переведенный текст |
| `application/interfaces/i_settings.py` | Интерфейс настроек | ключ (или get/set) | Значение настройки |

---

## 12. Application Layer - Results  

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `application/results/__init__.py` | Экспорт классов результатов | - | AppResult[T] |
| `application/results/app_result.py` | Result monad (Success/Failure) | данные или ошибка | AppResult[T] с методом .match() |

---

## 13. Application Layer - Database

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `application/database/__init__.py` | Экспорт БД модулей | - | DbSession |
| `application/database/db_session.py` | Интерфейс БД сессии | - | Методы begin(), commit(), rollback() |

---

## 14. Presentation Layer - Dialogs

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `presentation/dialogs/__init__.py` | Экспорт диалогов | - | ConverterDialog, ImportDialog и т.д. |
| `presentation/dialogs/converter_dialog.py` | Главный диалог конвертера | QgsInterface | Выбранные параметры импорта/экспорта |
| `presentation/dialogs/import_dialog.py` | Диалог импорта (параметры, фильтры) | DXFDocument | ImportConfigDTO |
| `presentation/dialogs/export_dialog.py` | Диалог экспорта (параметры, путь) | Active document | ExportConfigDTO |
| `presentation/dialogs/connection_dialog.py` | Диалог подключения к БД | - | ConnectionConfigDTO |
| `presentation/dialogs/schema_select_dialog.py` | Диалог выбора схемы БД | Список схем | Выбранная схема |

---

## 15. Presentation Layer - Widgets

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `presentation/widgets/__init__.py` | Экспорт виджетов | - | SelectableDXFTreeHandler и т.д. |
| `presentation/widgets/selectable_dxf_tree_handler.py` | Древо выбора сущностей DXF | DXFDocument | Список выбранных Entity |
| `presentation/widgets/viewer_dxf_tree_handler.py` | Древо просмотра структуры DXF | DXFDocument | Информация о выбранной сущности |
| `presentation/widgets/qgis_layer_sync_manager.py` | Синхронизация слоев QGIS | DXFDocument, QGIS layer | Синхронизированные слои |
| `presentation/widgets/preview_components.py` | Компоненты предпросмотра (canvas, tools) | Данные для отображения | Отрисованная геометрия |

---

## 16. Presentation Layer - Workers

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `presentation/workers/__init__.py` | Экспорт workers | - | LongTaskWorker |
| `presentation/workers/long_task_worker.py` | Worker для долгих операций в отдельном потоке | Функция, параметры | Результат, сигналы прогресса |

---

## 17. Presentation Layer - Services

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `presentation/services/__init__.py` | Экспорт сервисов | - | DialogService, StateService и т.д. |
| `presentation/services/dialog_service.py` | Управление диалогами (отображение, скрытие) | Dialog, параметры | QDialog |
| `presentation/services/state_service.py` | Управление состоянием UI (история, текущее состояние) | Действие | State change |
| `presentation/services/notification_service.py` | Уведомления и сообщения | Текст, тип | Показанное уведомление |
| `presentation/services/progress_service.py` | Управление прогрессом операций | Текущее значение, максимум | UI прогресс бара |
| `presentation/services/theme_service.py` | Управление темой (светлая/темная) | Новая тема | Примененная тема |

---

## 18. Infrastructure Layer - Database

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `infrastructure/database/__init__.py` | Экспорт БД реализаций | - | PostgreSQL имплементации |
| `infrastructure/database/db_session_impl.py` | Реализация БД сессии | Конфиг подключения | DbSession с ACID операциями |
| `infrastructure/database/postgresql_connection.py` | Подключение к PostgreSQL | Host, port, user, password, db | Открытое соединение |
| `infrastructure/database/document_repository.py` | Реализация репозитория документов | SQL запросы | CRUD операции для документов |
| `infrastructure/database/layer_repository.py` | Реализация репозитория слоев | SQL с PostGIS | CRUD операции для слоев |
| `infrastructure/database/entity_repository.py` | Реализация репозитория сущностей | Геометрия PostGIS | CRUD операции для сущностей |
| `infrastructure/database/repository_factory.py` | Фабрика для создания репозиториев | IConnection | Экземпляры репозиториев |

---

## 19. Infrastructure Layer - ezdxf

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `infrastructure/ezdxf/__init__.py` | Экспорт ezdxf модулей | - | DXFReader, DXFWriter |
| `infrastructure/ezdxf/dxf_reader.py` | Чтение DXF файлов (ezdxf library) | Путь к файлу | DXFDocument |
| `infrastructure/ezdxf/dxf_writer.py` | Запись DXF файлов | DXFDocument, путь | DXF файл на диске |
| `infrastructure/ezdxf/geometry_converter.py` | Конвертирование координат (DXF ← → WKT) | DXF координаты или WKT | Преобразованная геометрия |
| `infrastructure/ezdxf/dxf_validator.py` | Валидация DXF файлов | Путь к файлу | ValidationResult |
| `infrastructure/ezdxf/area_selector.py` | Выделение сущностей в области (XY bounds) | Bounds, DXFDocument | Список Entity в области |

---

## 20. Infrastructure Layer - QGIS

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `infrastructure/qgis/__init__.py` | Экспорт QGIS интеграций | - | QtLogger, QtSettings и т.д. |
| `infrastructure/qgis/qt_logger.py` | Имплементация логирования через Qt QMessageBox | message, level | Сообщение в лог QGIS |
| `infrastructure/qgis/qt_app_events.py` | Имплементация шины событий через Qt signals | Event | Qt signal отправлен |
| `infrastructure/qgis/qt_settings.py` | Имплементация настроек через QSettings | ключ | Значение из QSettings |
| `infrastructure/qgis/qt_event.py` | Базовое событие Qt | - | Qt event объект |

---

## 21. Infrastructure Layer - Localization

| Наименование модуля | Назначение | Входные данные | Выходные данные |
|---|---|---|---|
| `infrastructure/localization/__init__.py` | Экспорт i18n модулей | - | LocalizationManager |
| `infrastructure/localization/localization_manager.py` | Управления локализацией (язык, переводы) | Ключ, язык | Переведенный текст |
| `infrastructure/localization/language_file_loader.py` | Загрузка файлов перевода (.py или .json) | Путь к файлу | Словарь переводов |
| `infrastructure/localization/date_time_formatter.py` | Форматирование даты/времени по локали | datetime объект, язык | Форматированная строка |
| `infrastructure/localization/string_encoder.py` | Кодирование строк (UTF-8, ASCII) | Строка, кодировка | Закодированная строка |

---

## Резюме

- **Всего модулей**: 60+ Python файлов (.py)
- **Всего пакетов**: 20 архитектурных пакетов
- **Слоев архитектуры**: 4 (Domain, Application, Presentation, Infrastructure)
- **Интерфейсов**: 15+ (SOLID принцип DIP)
- **Реализаций**: 30+ конкретных классов

**Организация**:
- Domain слой: сущности, репозитории, сервисы, value objects
- Application слой: use cases, DTOs, маппсеры, события, результаты
- Presentation слой: диалоги, виджеты, workers, сервисы
- Infrastructure слой: БД, ezdxf, QGIS API, локализация

✅ **Статус**: Все модули задокументированы
