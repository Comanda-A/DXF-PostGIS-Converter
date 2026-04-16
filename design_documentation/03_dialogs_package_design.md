# Проектирование пакета presentation/dialogs

## Исходная диаграмма классов пакета «dialogs»

```uml
@startuml

class QDialog

class ConverterDialog {
  - active_doc_service: ActiveDocumentService
  - use_cases: Dict[str, UseCase]
  - tree_handler: SelectableDxfTreeHandler
  - app_events: IAppEvents
  
  + show_import_dialog()
  + show_export_dialog()
  + refresh_document_tree()
  + handle_import_result(result, report)
}

class ImportDialog {
  - connection_config: ConnectionConfigDTO
  - import_configs: List[ImportConfigDTO]
  - progress_worker: LongTaskWorker
  
  + get_connection_config(): ConnectionConfigDTO
  + get_import_configs(): List[ImportConfigDTO]
  + show_progress(percentage)
}

class ExportDialog {
  - connection_config: ConnectionConfigDTO
  - export_configs: List[ExportConfigDTO]
  - progress_worker: LongTaskWorker
  
  + get_connection_config(): ConnectionConfigDTO
  + get_export_configs(): List[ExportConfigDTO]
  + show_progress(percentage)
}

class ConnectionDialog {
  - connection_config: ConnectionConfigDTO
  - validators: Dict[str, Validator]
  
  + get_connection_config(): ConnectionConfigDTO
  + validate_connection(): bool
}

class SchemaSelectDialog {
  - schemas: List[str]
  - selected_schema: str
  
  + get_selected_schema(): str
}

QDialog <|-- ConverterDialog : наследует
QDialog <|-- ImportDialog : наследует
QDialog <|-- ExportDialog : наследует
QDialog <|-- ConnectionDialog : наследует
QDialog <|-- SchemaSelectDialog : наследует

ConverterDialog *-- "1" SelectableDxfTreeHandler : содержит
ConverterDialog -- "1" ImportDialog : создает
ConverterDialog -- "1" ExportDialog : создает
ConverterDialog -- "1" ConnectionDialog : создает
ConverterDialog -- "1" SchemaSelectDialog : создает

@enduml
```

---

## Описание классов пакета «dialogs»

| Класс | Назначение | Тип |
|-------|-----------|-----|
| **ConverterDialog** | Главный диалог плагина. Орхестрирует все операции, управляет документами, показывает дерево файлов, запускает процессы импорта/экспорта. | dialog |
| **ImportDialog** | Диалог импорта DXF файлов в БД. Содержит форму выбора файлов, конфиг подключения, параметры импорта. | dialog |
| **ExportDialog** | Диалог экспорта данных из БД в DXF файлы. Параметры экспорта, выбор слоев, целевая директория. | dialog |
| **ConnectionDialog** | Диалог настройки подключения к БД. Параметры хоста, портака, базы данных, авторизация. | dialog |
| **SchemaSelectDialog** | Диалог выбора схемы БД. Список доступных схем для размещения таблиц. | dialog |

---

## Диаграммы последовательностей взаимодействия объектов

### Нормальный ход событий: Импорт файла через диалоги

```uml
@startuml

participant "User" as User
participant "ConverterDialog" as MainDialog
participant "ImportDialog" as ImportDlg
participant "ConnectionDialog" as ConnDlg
participant "LongTaskWorker" as Worker
participant "ImportUseCase" as UseCase

-> User: Нажимает 'Import'
activate User

User -> MainDialog: show_import_dialog()
activate MainDialog

MainDialog -> ImportDlg: create()
activate ImportDlg
ImportDlg --> MainDialog: instance
deactivate ImportDlg

MainDialog -> ImportDlg: show()
ImportDlg -> ImportDlg: render UI
ImportDlg --> MainDialog: shown

User -> ImportDlg: выбирает файлы и параметры
activate ImportDlg

User -> ImportDlg: нажимает 'Next' для подключения
deactivate ImportDlg

ImportDlg -> ConnDlg: show_connection_dialog()
activate ConnDlg
ConnDlg --> ImportDlg: instance
deactivate ConnDlg

User -> ConnDlg: вводит параметры БД
activate ConnDlg
deactivate ConnDlg

User -> ImportDlg: нажимает 'Start Import'
activate ImportDlg

ImportDlg -> Worker: create(UseCase.execute)
activate Worker

Worker -> UseCase: execute(connection, configs)
activate UseCase

UseCase --> Worker: progress updates
Worker --> ImportDlg: progress signals

UseCase --> Worker: Result[Unit]
deactivate UseCase

Worker -> ImportDlg: finished signal with result
deactivate Worker

ImportDlg -> ImportDlg: show_result_report()
deactivate ImportDlg

ImportDlg --> MainDialog: close
deactivate ImportDlg

MainDialog -> MainDialog: refresh_document_tree()
deactivate MainDialog

<-- User: Import completed
deactivate User

@enduml
```

### Нормальный ход событий: Экспорт файла

```uml
@startuml

participant "User" as User
participant "ConverterDialog" as MainDialog
participant "ExportDialog" as ExportDlg
participant "ConnectionDialog" as ConnDlg
participant "LongTaskWorker" as Worker
participant "ExportUseCase" as UseCase

-> User: Нажимает 'Export'
activate User

User -> MainDialog: show_export_dialog()
activate MainDialog

MainDialog -> ExportDlg: create()
activate ExportDlg

User -> ExportDlg: выбирает слои и параметры
activate ExportDlg
deactivate ExportDlg

User -> ExportDlg: нажимает 'Next'
activate ExportDlg

ExportDlg -> ConnDlg: show_connection_dialog()
activate ConnDlg

User -> ConnDlg: вводит параметры БД
deactivate ConnDlg

ExportDlg -> Worker: create(UseCase.execute)
activate Worker

Worker -> UseCase: execute(connection, configs)
activate UseCase

UseCase --> Worker: progress updates
Worker --> ExportDlg: show_progress()

UseCase --> Worker: Result[Unit]
deactivate UseCase

Worker -> ExportDlg: finished signal
deactivate Worker

ExportDlg -> ExportDlg: show_result_report()
deactivate ExportDlg

MainDialog -> MainDialog: refresh_tree()
deactivate MainDialog

<-- User: Export completed
deactivate User

@enduml
```

### Прерывание процесса пользователем: Отмена импорта

```uml
@startuml

participant "User" as User
participant "ImportDialog" as ImportDlg
participant "LongTaskWorker" as Worker
participant "ImportUseCase" as UseCase

-> User: нажимает 'Start Import'
activate User

User -> ImportDlg: запускает импорт
activate ImportDlg

ImportDlg -> Worker: create(UseCase.execute)
activate Worker

Worker -> UseCase: execute()
activate UseCase

UseCase --> Worker: progress (30%)
Worker --> ImportDlg: progress signal

-> User: нажимает 'Cancel'
activate User

User -> ImportDlg: cancel_import()
deactivate User

ImportDlg -> Worker: cancel()
activate ImportDlg

Worker -> UseCase: cancel signal
UseCase -> UseCase: cleanup
UseCase --> Worker: cancelled
deactivate UseCase

Worker -> ImportDlg: cancelled signal
deactivate Worker

ImportDlg -> ImportDlg: show_cancel_dialog()
deactivate ImportDlg

<-- User: Import cancelled
deactivate User

@enduml
```

### Прерывание процесса системой: Ошибка при импорте

```uml
@startuml

participant "ImportDialog" as ImportDlg
participant "LongTaskWorker" as Worker
participant "ImportUseCase" as UseCase

-> ImportDlg: start_import()
activate ImportDlg

ImportDlg -> Worker: create(UseCase.execute)
activate Worker

Worker -> UseCase: execute()
activate UseCase

UseCase -> UseCase: validate connection
UseCase -> UseCase: Exception: Database connection failed

UseCase --> Worker: Result.fail(error)
deactivate UseCase

Worker -> Worker: capture exception

Worker -> ImportDlg: error signal

ImportDlg -> ImportDlg: show_error_message()

Worker --> ImportDlg: error message
deactivate Worker

deactivate ImportDlg

@enduml
```

---

## Уточненная диаграмма классов (с типами связей)

```uml
@startuml

class QDialog #DDDDDD {
  + show()
  + close()
  + setModal(bool)
}

class ConverterDialog {
  - active_doc_service: ActiveDocumentService
  - open_doc_use_case: OpenDocumentUseCase
  - import_use_case: ImportUseCase
  - export_use_case: ExportUseCase
  - select_entity_use_case: SelectEntityUseCase
  - select_area_use_case: SelectAreaUseCase
  - tree_handler: SelectableDxfTreeHandler
  - app_events: IAppEvents
  - logger: ILogger
  - localization: ILocalization
  
  + __init__()
  + closeEvent()
  + show_import_dialog()
  + show_export_dialog()
  + show_connection_dialog()
  + show_schema_selector()
  + refresh_document_tree()
  + on_import_finished(result, report)
  + on_export_finished(result, report)
  + on_error(error_message)
}

class ImportDialog {
  - file_list_widget: QListWidget
  - connection_config: ConnectionConfigDTO
  - import_configs: List[ImportConfigDTO]
  - progress_dialog: QProgressDialog
  - import_worker: LongTaskWorker
  
  + __init__(parent: QWidget)
  + show()
  + get_connection_config(): ConnectionConfigDTO
  + get_import_configs(): List[ImportConfigDTO]
  + start_import()
  + cancel_import()
  + on_progress(current: int, total: int)
  + on_import_finished(task_id, result)
  + show_result_dialog()
}

class ExportDialog {
  - layer_selector: QTreeWidget
  - output_path: str
  - connection_config: ConnectionConfigDTO
  - export_configs: List[ExportConfigDTO]
  - progress_dialog: QProgressDialog
  - export_worker: LongTaskWorker
  
  + __init__(parent: QWidget)
  + show()
  + get_connection_config(): ConnectionConfigDTO
  + get_export_configs(): List[ExportConfigDTO]
  + start_export()
  + cancel_export()
  + on_progress(current: int, total: int)
  + on_export_finished(task_id, result)
  + show_result_dialog()
}

class ConnectionDialog {
  - host_edit: QLineEdit
  - port_edit: QLineEdit
  - database_edit: QLineEdit
  - username_edit: QLineEdit
  - password_edit: QLineEdit
  - connection_config: ConnectionConfigDTO
  - validators: Dict[str, Validator]
  
  + __init__(parent: QWidget)
  + show()
  + get_connection_config(): ConnectionConfigDTO
  + validate_connection(): bool
  + test_connection()
  + on_connection_tested(success)
}

class SchemaSelectDialog {
  - schema_combo: QComboBox
  - schemas: List[str]
  - selected_schema: str
  
  + __init__(parent: QWidget, schemas: List[str])
  + show()
  + get_selected_schema(): str
}

QDialog <|-- ConverterDialog
QDialog <|-- ImportDialog
QDialog <|-- ExportDialog
QDialog <|-- ConnectionDialog
QDialog <|-- SchemaSelectDialog

ConverterDialog *-- "1" SelectableDxfTreeHandler : агрегирует
ConverterDialog -- "1" ImportDialog : зависимость (создает)
ConverterDialog -- "1" ExportDialog : зависимость (создает)
ConverterDialog -- "1" ConnectionDialog : зависимость (создает)
ConverterDialog -- "1" SchemaSelectDialog : зависимость (создает)

ImportDialog -- "1" LongTaskWorker : зависимость (создает)
ExportDialog -- "1" LongTaskWorker : зависимость (создает)

@enduml
```

---

## Детальная диаграмма классов (все поля и методы)

```uml
@startuml

class ConverterDialog {
  - active_doc_service: ActiveDocumentService
  - open_doc_use_case: OpenDocumentUseCase
  - import_use_case: ImportUseCase
  - export_use_case: ExportUseCase
  - select_entity_use_case: SelectEntityUseCase
  - select_area_use_case: SelectAreaUseCase
  - close_document_use_case: CloseDocumentUseCase
  - data_viewer_use_case: DataViewerUseCase
  - tree_handler: SelectableDxfTreeHandler
  - app_events: IAppEvents
  - logger: ILogger
  - localization: ILocalization
  - current_worker: Optional[LongTaskWorker]
  
  + __init__()
  + closeEvent(event: QCloseEvent)
  + show_import_dialog() : int
  + show_export_dialog() : int
  + show_connection_dialog() : Optional[ConnectionConfigDTO]
  + show_schema_selector(schemas: List[str]) : str
  + refresh_document_tree() : void
  + on_import_finished(task_id: int, result: Any) : void
  + on_export_finished(task_id: int, result: Any) : void
  + on_error(error_message: str) : void
  + on_import_progress(current: int, total: int) : void
  + on_export_progress(current: int, total: int) : void
  + on_worker_cancelled() : void
  - _create_ui() : void
  - _connect_signals() : void
  - _setup_toolbar() : void
  - _setup_tree_widget() : void
  - _load_recent_documents() : void
  - _handle_import_error(error: str) : void
  - _handle_export_error(error: str) : void
  - _show_result_dialog(title: str, report: str) : void
}

class ImportDialog {
  - file_list_widget: QListWidget
  - mapping_mode_combo: QComboBox
  - layer_schema_edit: QLineEdit
  - file_schema_edit: QLineEdit
  - connection_config: Optional[ConnectionConfigDTO]
  - import_configs: List[ImportConfigDTO]
  - progress_dialog: QProgressDialog
  - import_worker: Optional[LongTaskWorker]
  - current_task_id: int
  
  + __init__(parent: QWidget)
  + show() : int
  + get_connection_config() : Optional[ConnectionConfigDTO]
  + get_import_configs() : List[ImportConfigDTO]
  + start_import() : void
  + cancel_import() : void
  + on_progress(current: int, total: int) : void
  + on_import_finished(task_id: int, result: Any) : void
  + on_import_error(error: str) : void
  + show_result_dialog(success: bool, report: str) : void
  + _add_files(file_paths: List[str]) : void
  + _remove_selected_files() : void
  + _validate_inputs() : bool
  + _create_ui() : void
  + _connect_signals() : void
}

class ExportDialog {
  - layer_tree_widget: QTreeWidget
  - output_dir_edit: QLineEdit
  - filename_pattern_edit: QLineEdit
  - export_mode_combo: QComboBox
  - connection_config: Optional[ConnectionConfigDTO]
  - export_configs: List[ExportConfigDTO]
  - progress_dialog: QProgressDialog
  - export_worker: Optional[LongTaskWorker]
  - current_task_id: int
  
  + __init__(parent: QWidget)
  + show() : int
  + get_connection_config() : Optional[ConnectionConfigDTO]
  + get_export_configs() : List[ExportConfigDTO]
  + start_export() : void
  + cancel_export() : void
  + on_progress(current: int, total: int) : void
  + on_export_finished(task_id: int, result: Any) : void
  + on_export_error(error: str) : void
  + show_result_dialog(success: bool, report: str) : void
  + _select_output_directory() : void
  + _validate_inputs() : bool
  + _create_ui() : void
  + _connect_signals() : void
}

class ConnectionDialog {
  - host_edit: QLineEdit
  - port_edit: QSpinBox
  - database_edit: QLineEdit
  - username_edit: QLineEdit
  - password_edit: QLineEdit
  - test_button: QPushButton
  - connection_config: Optional[ConnectionConfigDTO]
  - is_connected: bool
  
  + __init__(parent: QWidget)
  + show() : int
  + get_connection_config() : Optional[ConnectionConfigDTO]
  + validate_connection() : bool
  + test_connection() : void
  + on_connection_tested(success: bool, message: str) : void
  + set_connection_config(config: ConnectionConfigDTO) : void
  - _load_connection_config() : void
  - _save_connection_config() : void
  - _validate_inputs() : bool
  - _create_ui() : void
  - _connect_signals() : void
}

class SchemaSelectDialog {
  - schema_combo: QComboBox
  - schemas: List[str]
  - selected_schema: str
  
  + __init__(parent: QWidget, schemas: List[str])
  + show() : int
  + get_selected_schema() : str
  - _populate_schemas() : void
}

@enduml
```

---

## Описание методов класса «ConverterDialog»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | - | None | Инициализирует главный диалог, устанавливает UI и сигналы |
| **closeEvent** | event: QCloseEvent | None | Обработчик закрытия окна, сохраняет состояние |
| **show_import_dialog** | - | int | Показывает диалог импорта, возвращает код результата |
| **show_export_dialog** | - | int | Показывает диалог экспорта, возвращает код результата |
| **show_connection_dialog** | - | Optional[ConnectionConfigDTO] | Показывает диалог подключения БД |
| **show_schema_selector** | schemas: List[str] | str | Показывает диалог выбора схемы БД |
| **refresh_document_tree** | - | None | Обновляет дерево документов на экране |
| **on_import_finished** | task_id: int, result: Any | None | Обработчик завершения импорта |
| **on_export_finished** | task_id: int, result: Any | None | Обработчик завершения экспорта |
| **on_error** | error_message: str | None | Обработчик ошибок |

---

## Описание методов класса «ImportDialog»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | parent: QWidget | None | Инициализирует диалог импорта |
| **show** | - | int | Показывает модальный диалог |
| **get_connection_config** | - | Optional[ConnectionConfigDTO] | Получает конфиг подключения БД |
| **get_import_configs** | - | List[ImportConfigDTO] | Получает конфиги импорта файлов |
| **start_import** | - | None | Запускает процесс импорта |
| **cancel_import** | - | None | Отменяет процесс импорта |
| **on_progress** | current: int, total: int | None | Обработчик прогресса |
| **on_import_finished** | task_id: int, result: Any | None | Обработчик завершения |
| **show_result_dialog** | success: bool, report: str | None | Показывает результат операции |

---

## Описание методов класса «ExportDialog»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | parent: QWidget | None | Инициализирует диалог экспорта |
| **show** | - | int | Показывает модальный диалог |
| **get_connection_config** | - | Optional[ConnectionConfigDTO] | Получает конфиг БД |
| **get_export_configs** | - | List[ExportConfigDTO] | Получает конфиги экспорта |
| **start_export** | - | None | Запускает процесс экспорта |
| **cancel_export** | - | None | Отменяет процесс экспорта |
| **on_progress** | current: int, total: int | None | Обработчик прогресса |
| **on_export_finished** | task_id: int, result: Any | None | Обработчик завершения |
| **show_result_dialog** | success: bool, report: str | None | Показывает результат |

---

## Описание методов класса «ConnectionDialog»

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| **__init__** | parent: QWidget | None | Инициализирует диалог подключения |
| **show** | - | int | Показывает модальный диалог |
| **get_connection_config** | - | Optional[ConnectionConfigDTO] | Получает конфиг подключения |
| **validate_connection** | - | bool | Проверяет корректность параметров |
| **test_connection** | - | None | Тестирует подключение к БД |
| **on_connection_tested** | success: bool, message: str | None | Обработчик результата теста |
| **set_connection_config** | config: ConnectionConfigDTO | None | Устанавливает конфиг подключения |

---

## Заключение

Пакет **dialogs** реализует весь пользовательский интерфейс приложения через систему модальных и немодальных диалогов. ConverterDialog выступает главной точкой входа, оркестрируя все остальные диалоги и управляя взаимодействием с use cases. Использование LongTaskWorker позволяет выполнять длительные операции без блокировки UI, обеспечивая отзывчивый интерфейс для пользователя.
