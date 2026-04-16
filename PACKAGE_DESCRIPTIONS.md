# Описание пакетов DXF-PostGIS Converter

| Пакет | Описание |
|-------|---------|
| **domain/entities** | Основные сущности предметной области: DXFBase, DXFDocument, DXFLayer, DXFEntity, DXFContent. Содержат инкапсулированное состояние и бизнес-поведение. |
| **domain/repositories** | Интерфейсы для доступа к данным: IRepository, IDocumentRepository, ILayerRepository, IEntityRepository, IActiveDocumentRepository. Определяют контракты для хранилищ. |
| **domain/services** | Интерфейсы доменных сервисов: IDXFReader (чтение DXF), IDXFWriter (запись DXF), IAreaSelector (выбор по площади). Содержат высокоуровневую бизнес-логику. |
| **domain/value_objects** | Неизменяемые объекты значений: Result[T] (обертка результата), ConnectionConfig (конфиг БД), DxfEntityType (тип элемента), AreaSelectionParams (параметры выбора). |
| **application/use_cases** | Варианты использования приложения: ImportUseCase, ExportUseCase, OpenDocumentUseCase, SelectEntityUseCase, SelectAreaUseCase, CloseDocumentUseCase, DataViewerUseCase. Оркестрируют бизнес-процессы. |
| **application/services** | Прикладные сервисы: ActiveDocumentService (управление открытыми документами), ConnectionConfigService (конфигурация подключения). Обеспечивают бизнес-функции приложения. |
| **application/mappers** | Преобразователи между слоями: DXFMapper (Entity → DTO). Изолируют домен от представления. |
| **application/dtos** | Data Transfer Objects: DXFDocumentDTO, DXFLayerDTO, DXFEntityDTO, ImportConfigDTO, ExportConfigDTO. Структуры для передачи данных между слоями. |
| **application/events** | Интерфейсы событий: IEvent[T] (базовое событие), IAppEvents (события приложения). Обеспечивают слабую связанность компонентов. |
| **application/interfaces** | Интерфейсы для инфраструктуры: ILogger (логирование), ILocalization (локализация), ISettings (настройки). Инверсия зависимостей для фреймворков. |
| **application/results** | Результаты операций: AppResult[T] (обертка результата приложения). Унифицированная обработка успехов и ошибок. |
| **application/database** | Управление БД: DBSession (сессия подключения). Промежуточный слой для работы с базой данных. |
| **presentation/dialogs** | Qt диалоги: ConverterDialog (главный), ImportDialog, ExportDialog, ConnectionDialog. Главные окна и диалоги интерфейса. |
| **presentation/widgets** | Qt компоненты: SelectableDxfTreeHandler (дерево с выбором), ViewerDxfTreeHandler (просмотр), QGISLayerSyncManager (синхронизация), PreviewComponents (предпросмотр). |
| **presentation/workers** | Фоновые потоки: LongTaskWorker (выполняет длительные операции в отдельном потоке). Предотвращает замораживание UI. |
| **presentation/services** | Вспомогательные сервисы: DialogTranslator (локализация диалогов), AreaSelectionController (контроллер выбора). Поддерживают диалоги. |
| **infrastructure/database** | PostgreSQL/PostGIS реализация: RepositoryFactory (создание репозиториев), ConnectionFactory (создание соединений), ActiveDocumentRepository, postgis/ (конкретные реализации репозиториев). |
| **infrastructure/ezdxf** | Работа с DXF файлами: DXFReader (реализует IDXFReader чтение), DXFWriter (реализует IDXFWriter сохранение), AreaSelector (реализует IAreaSelector выбор). |
| **infrastructure/qgis** | Qt/QGIS интеграция: Logger (реализует ILogger), QtAppEvents (реализует IAppEvents), QtSettings (реализует ISettings), QtEvent (реализует IEvent). |
| **infrastructure/localization** | Локализация: LocalizationManager (реализует ILocalization с поддержкой multiple языков из i18n/). |
