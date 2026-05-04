# Индекс документации проектирования пакетов

Папка `design_documentation/` содержит детальное проектирование каждого пакета приложения для диплома.

## 📑 Содержание файлов

### 1. Пакеты Domain Layer

#### [01_entities_package_design.md](01_entities_package_design.md)
**Пакет: `domain/entities`**

Содержит базовые сущности предметной области приложения:
- **DXFBase** — абстрактный базовый класс с UUID и флагом выделения
- **DXFDocument** — документ DXF (файл с метаданными)
- **DXFLayer** — слой DXF (группа элементов)
- **DXFEntity** — элемент чертежа (точка, линия, круг и т.д.)
- **DXFContent** — бинарное содержимое файла

**Содержит:**
- ✅ Исходная диаграмма классов (UML)
- ✅ Таблица описания классов
- ✅ 4 диаграммы последовательностей (нормальный ход, 2 варианта прерываний)
- ✅ Уточненная диаграмма (с типами связей)
- ✅ Детальная диаграмма (все поля и методы)
- ✅ Таблицы описания полей и методов

---

#### [04_repositories_package_design.md](04_repositories_package_design.md)
**Пакет: `domain/repositories`**

Интерфейсы для доступа к данным (паттерн Repository):
- **IRepository** — базовый интерфейс (CRUD операции)
- **IDocumentRepository** — работа с документами
- **ILayerRepository** — работа со слоями
- **IEntityRepository** — работа с элементами
- **IContentRepository** — работа с содержимым
- **IActiveDocumentRepository** — управление открытыми документами в памяти
- **IConnection** — интерфейс подключения к БД
- **IConnectionFactory**, **IRepositoryFactory** — Factory паттерны

**Содержит:**
- ✅ Полное описание всех интерфейсов
- ✅ Диаграммы последовательностей взаимодействия
- ✅ Детальное описание методов

---

### 2. Пакеты Application Layer

#### [02_use_cases_package_design.md](02_use_cases_package_design.md)
**Пакет: `application/use_cases`**

Варианты использования (Use Cases) приложения:
- **OpenDocumentUseCase** — открытие DXF файла
- **ImportUseCase** — импорт DXF в БД
- **ExportUseCase** — экспорт DXF из БД в файл
- **SelectEntityUseCase** — выбор отдельного элемента
- **SelectAreaUseCase** — выбор элементов по площади
- **CloseDocumentUseCase** — закрытие документа
- **DataViewerUseCase** — просмотр данных

**Содержит:**
- ✅ Исходная диаграмма классов
- ✅ Таблица описания use cases
- ✅ 4 диаграммы последовательностей (нормальные ходы и прерывания)
- ✅ Уточненная и детальная диаграммы
- ✅ Полное описание методов каждого use case

---

#### [05_dtos_package_design.md](05_dtos_package_design.md)
**Пакет: `application/dtos`**

Data Transfer Objects для передачи данных между слоями:
- **DXFDocumentDTO** — DTO документа
- **DXFLayerDTO** — DTO слоя
- **DXFEntityDTO** — DTO элемента
- **ConnectionConfigDTO** — конфиг подключения
- **ImportConfigDTO** — конфиг импорта
- **ExportConfigDTO** — конфиг экспорта

**Содержит:**
- ✅ Исходная диаграмма классов
- ✅ Таблица описания классов
- ✅ 4 диаграммы последовательностей
- ✅ Уточненная и детальная диаграммы
- ✅ Полное описание полей и методов

---

#### [06_mappers_package_design.md](06_mappers_package_design.md)
**Пакет: `application/mappers`**

Преобразователи между слоями:
- **DXFMapper** — преобразование Entity → DTO с поддержкой вложенных объектов
- **ConnectionConfigMapper** — маппинг конфига подключения
- **ImportConfigMapper** — маппинг конфига импорта

**Содержит:**
- ✅ Исходная диаграмма классов
- ✅ Таблица описания классов
- ✅ 4 диаграммы последовательностей
- ✅ Уточненная и детальная диаграммы
- ✅ Полное описание методов

---

### 3. Пакеты Presentation Layer

#### [03_dialogs_package_design.md](03_dialogs_package_design.md)
**Пакет: `presentation/dialogs`**

Qt диалоги главного интерфейса:
- **ConverterDialog** — главный диалог плагина
- **ImportDialog** — диалог импорта DXF
- **ExportDialog** — диалог экспорта в DXF
- **ConnectionDialog** — настройка БД подключения
- **SchemaSelectDialog** — выбор схемы БД

**Содержит:**
- ✅ Полное описание всех диалогов
- ✅ Диаграммы взаимодействия между диалогами
- ✅ Диаграммы последовательностей (нормальные и исключительные ситуации)
- ✅ Детальное описание методов и сигналов

---

#### [07_widgets_package_design.md](07_widgets_package_design.md)
**Пакет: `presentation/widgets`**

Qt виджеты (компоненты UI):
- **SelectableDxfTreeHandler** — дерево с выбором элементов, ленивая загрузка
- **ViewerDxfTreeHandler** — просмотр структуры в режиме просмотра
- **QGISLayerSyncManager** — синхронизация слоев с QGIS canvas
- **ZoomableGraphicsView** — масштабируемое представление графики
- **PreviewDialog** — диалог предпросмотра SVG файлов

**Содержит:**
- ✅ Полное описание всех компонентов UI
- ✅ Диаграммы взаимодействия между виджетами
- ✅ Диаграммы последовательностей (4 сценария)
- ✅ Полное описание методов и полей

---

#### [08_workers_package_design.md](08_workers_package_design.md)
**Пакет: `presentation/workers`**

Фоновые потоки для асинхронной обработки:
- **LongTaskWorker** — выполнение длительных операций в отдельном потоке (PyQt QThread)

**Содержит:**
- ✅ Полное описание LongTaskWorker
- ✅ Диаграммы жизненного цикла потока
- ✅ Диаграммы последовательностей (4 сценария)
- ✅ Примеры использования с функциями поддержки прогресса

---

### 4. Пакеты Infrastructure Layer

#### [09_database_package_design.md](09_database_package_design.md)
**Пакет: `infrastructure/database`**

PostgreSQL/PostGIS реализация репозиториев:
- **PostgreSQLConnection** — управление подключением к БД
- **DocumentRepository** — CRUD операции с документами
- **LayerRepository** — CRUD операции со слоями
- **EntityRepository** — CRUD операции с сущностями
- **RepositoryFactory** — создание репозиториев с общим подключением

**Содержит:**
- ✅ Полное описание всех репозиториев
- ✅ Схема базы данных (таблицы и индексы)
- ✅ Диаграммы последовательностей (4 сценария)
- ✅ Полное описание всех методов и SQL операций

---

#### [10_ezdxf_package_design.md](10_ezdxf_package_design.md)
**Пакет: `infrastructure/ezdxf`**

Работа с DXF файлами через библиотеку ezdxf:
- **DXFReader** — чтение DXF файлов и преобразование в доменные сущности
- **DXFWriter** — запись доменных сущностей в DXF файлы
- **GeometryConverter** — преобразование геометрии между DXF и PostGIS
- **DXFValidator** — валидация DXF файлов и структур
- **AreaSelector** — выбор сущностей по геометрическим областям

**Содержит:**
- ✅ Полное описание всех компонентов ezdxf
- ✅ Диаграммы преобразования форматов
- ✅ Диаграммы последовательностей (4 сценария)
- ✅ Таблица поддерживаемых типов DXF сущностей

---

#### [11_qgis_package_design.md](11_qgis_package_design.md)
**Пакет: `infrastructure/qgis`**

Qt/QGIS интеграция через PyQt5:
- **QtLogger** — логирование в QGIS Message Bar и файлы
- **QtAppEvents** — управление событиями приложения через QGIS сигналы
- **QtSettings** — хранение настроек в QSettings (Registry/config)
- **QtEvent** — представление события приложения

**Содержит:**
- ✅ Полное описание QGIS интеграции
- ✅ Типы событий приложения (document_opened, selections_changed и т.д.)
- ✅ Структура хранения настроек (Windows Registry, Linux config)
- ✅ Диаграммы последовательностей (4 сценария)

---

#### [12_localization_package_design.md](12_localization_package_design.md)
**Пакет: `infrastructure/localization`**

Многоязычная поддержка интерфейса:
- **LocalizationManager** — управление переводами и языками
- **LanguageFileLoader** — загрузка файлов переводов (JSON, Python)
- **DateTimeFormatter** — форматирование дат/времени по языку
- **StringEncoder** — работа с кодировками (UTF-8, прочие)

**Содержит:**
- ✅ Полное описание системы локализации
- ✅ Структура файлов переводов (JSON, Python)
- ✅ Примеры использования tr() и tr_with_params()
- ✅ Диаграммы последовательностей (4 сценария)

---

#### [13_domain_services_package_design.md](13_domain_services_package_design.md)
**Пакет: `domain/services` + `domain/value_objects`**

Контракты сервисного слоя и общие value objects:
- **IAreaSelector** — выбор handle сущностей по области
- **IDXFReader** — чтение DXF-файла и SVG preview
- **IDXFWriter** — запись DXF-документа и выборочное сохранение по handle
- **ConnectionConfig** — конфигурация подключения к БД
- **AreaSelectionParams** — параметры геометрического выбора
- **SelectionRule**, **ShapeType**, **SelectionMode** — перечисления параметров выбора
- **DxfEntityType** — перечень поддерживаемых типов DXF-сущностей
- **Result** — унифицированный результат операции
- **Unit** — пустой тип для операций без полезного значения

**Содержит:**
- ✅ Исходная диаграмма классов
- ✅ Таблица описания классов
- ✅ 3 диаграммы последовательностей (нормальный ход и 2 варианта прерываний)
- ✅ Уточненная и детальная диаграммы
- ✅ Полные таблицы полей и методов для сервисов и value objects

---

### 5. Актуализированные отчеты Infrastructure Layer (Mermaid)

#### [21_infrastructure_ezdxf_package_report.md](21_infrastructure_ezdxf_package_report.md)
**Пакет: `infrastructure/ezdxf`**

Актуализированный отчет по текущей реализации:
- ✅ Mermaid диаграмма классов
- ✅ Mermaid диаграммы последовательностей
- ✅ Таблицы классов/методов

#### [22_infrastructure_qgis_package_report.md](22_infrastructure_qgis_package_report.md)
**Пакет: `infrastructure/qgis`**

Актуализированный отчет по текущей реализации:
- ✅ Mermaid диаграмма классов
- ✅ Mermaid диаграммы последовательностей
- ✅ Таблицы классов/методов

#### [23_infrastructure_database_package_report.md](23_infrastructure_database_package_report.md)
**Пакет: `infrastructure/database`**

Актуализированный отчет по текущей реализации:
- ✅ Mermaid диаграмма классов
- ✅ Mermaid диаграммы последовательностей
- ✅ Таблицы классов/методов

---

## 🎯 Структура каждого файла проектирования

Каждый файл проектирования пакета содержит:

### 1️⃣ Исходная диаграмма классов
- Классы пакета в виде UML диаграммы
- Отношения между классами (использует, создает, наследует и т.д.)
- Только внутренние связи пакета

### 2️⃣ Таблица описания классов
| Класс | Назначение | Тип |
| - | - | - |

### 3️⃣ Диаграммы последовательностей взаимодействия объектов
По **4 сценариям**:
1. **Нормальный ход событий** — успешное выполнение основного процесса
2. **Нормальный ход событий** (альтернативный) — альтернативный успешный сценарий
3. **Прерывание процесса пользователем** — отмена/отключение пользователем
4. **Прерывание процесса системой** — исключение, ошибка, сбой

Диаграммы созданы в формате UML PlantUML

### 4️⃣ Уточненная диаграмма классов
- Все поля класса с модификаторами доступа
- Все методы с параметрами и возвращаемыми типами
- **Типы связей:**
  - `*--` (агрегация) — постоянная зависимость
  - `--` (зависимость) — создаваемые объекты
  - `<|--` (наследование)

### 5️⃣ Детальная диаграмма классов
- Полное описание всех полей
- Все методы с сигнатурами
- Используется в диаграмме доступность полей

### 6️⃣ Таблицы описания полей и методов
| Поле/Название | Тип | Модификатор | Описание |
| - | - | - | - |

| Название | Параметры | Возвращает | Описание |
| - | - | - | - |

---

## 📊 Принципы проектирования

### ✅ Clean Architecture
- **Domain** — независим от фреймворков, чистая бизнес-логика
- **Application** — сценарии использования, оркестрация
- **Presentation** — UI, диалоги, взаимодействие с пользователем
- **Infrastructure** — реализация интерфейсов, внешние сервисы

### ✅ SOLID принципы
- **S** — Single Responsibility — каждый класс одну ответственность
- **O** — Open/Closed — открыт для расширения, закрыт для изменения
- **L** — Liskov Substitution — interface контракты соблюдаются
- **I** — Interface Segregation — узкие интерфейсы
- **D** — Dependency Inversion — зависимости на интерфейсы, не реализации

### ✅ Design Patterns
- **Factory** — создание объектов (RepositoryFactory, ConnectionFactory)
- **Repository** — доступ к данным (IRepository и наследники)
- **UseCase** — сценарии использования
- **DTO** — передача данных между слоями
- **Mapper** — преобразование между слоями
- **Strategy** — выбор алгоритмов (SelectionMode и т.д.)
- **Observer** — события и сигналы (PyQt signals)

### ✅ Направление зависимостей
```
Presentation → Application → Domain
Presentation → Infrastructure (для интерфейсов)
Infrastructure → Domain (реализует интерфейсы)
Domain ← Все (используют domain entities и interfaces)
```

---

## 📝 Статус документации

| Файл | Статус | Примечание |
|------|--------|-----------|
| 01_entities_package_design.md | ✅ Готово | Полное описание сущностей |
| 02_use_cases_package_design.md | ✅ Готово | Все варианты использования |
| 03_dialogs_package_design.md | ✅ Готово | Qt диалоги и UI |
| 04_repositories_package_design.md | ✅ Готово | Интерфейсы доступа к данным |
| 05_dtos_package_design.md | ✅ Готово | Data Transfer Objects |
| 06_mappers_package_design.md | ✅ Готово | Преобразователи слоев |
| 07_widgets_package_design.md | ✅ Готово | Qt компоненты и виджеты |
| 08_workers_package_design.md | ✅ Готово | Асинхронные рабочие потоки |
| 09_database_package_design.md | ✅ Готово | PostgreSQL/PostGIS реализация |
| 10_ezdxf_package_design.md | ✅ Готово | Работа с DXF файлами |
| 11_qgis_package_design.md | ✅ Готово | QGIS интеграция и события |
| 12_localization_package_design.md | ✅ Готово | Локализация интерфейса |

**Итого: 12/12 файлов завершено (100%)** 🎉

---

## 🔗 Связь с остальной документацией

- [PACKAGE_DESCRIPTIONS.md](../PACKAGE_DESCRIPTIONS.md) — Краткие описания всех пакетов
- [PACKAGES_INTERACTION_DETAILED.md](../PACKAGES_INTERACTION_DETAILED.md) — Взаимодействие пакетов между слоями
