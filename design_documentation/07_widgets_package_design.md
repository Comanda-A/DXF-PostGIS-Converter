# Проектирование пакета widgets

**Пакет**: `presentation/widgets`

**Назначение**: UI компоненты для представления и взаимодействия с DXF структурами, включая виджеты дерева, синхронизацию слоев QGIS и компоненты предпросмотра.

**Расположение**: `src/presentation/widgets/`

---

## 1. Исходная диаграмма классов (внутренние отношения)

```plantuml
@startuml presentation_widgets_original

!define ABSTRACT abstract
!define INTERFACE interface

package "presentation.widgets" {
    INTERFACE QObject
    INTERFACE QWidget
    INTERFACE QTreeWidget
    
    class SelectableDxfTreeHandler {
        - tree_widget: QTreeWidget
        - item_to_dto: list[tuple]
        - close_doc_use_case: CloseDocumentUseCase
        - select_entity_use_case: SelectEntityUseCase
        + update_tree()
        + clear_tree()
        + on_item_check_changed()
        + add_remove_button_to_item()
    }
    
    class ViewerDxfTreeHandler {
        - tree_widget: QTreeWidget
        - item_to_dto: list[tuple]
        - active_doc_service: ActiveDocumentService
        - localization: ILocalization
        + update_tree()
        + clear_tree()
        + highlight_entity()
        + on_item_double_click()
    }
    
    class QGISLayerSyncManager {
        - canvas: QgsMapCanvas
        - layer_map: dict[str, QgsVectorLayer]
        - active_doc_service: ActiveDocumentService
        - export_service: ExportService
        + add_layer()
        + remove_layer()
        + sync_selection()
        + on_selection_changed()
    }
    
    class ZoomableGraphicsView {
        - zoom_factor: float
        - transform: QTransform
        + wheelEvent()
        + mouseDoubleClickEvent()
        + resetView()
        + scale()
    }
    
    class PreviewDialog {
        - svg_path: str
        - view: ZoomableGraphicsView
        - localization: LocalizationManager
        + setup_ui()
        + create_instructions()
        + create_control_buttons()
    }
    
    SelectableDxfTreeHandler --|> QObject
    ViewerDxfTreeHandler --|> QObject
    QGISLayerSyncManager --|> QObject
    ZoomableGraphicsView --|> QGraphicsView
    PreviewDialog --|> QDialog
    PreviewDialog *-- ZoomableGraphicsView
}

@enduml
```

---

## 2. Таблица описания классов

| Класс | Назначение | Тип |
|-------|-----------|-----|
| **SelectableDxfTreeHandler** | Обработчик дерева DXF с поддержкой выбора сущностей и ленивую загрузков | Handler |
| **ViewerDxfTreeHandler** | Обработчик дерева DXF в режиме просмотра с подсветкой выбранных элементов | Handler |
| **QGISLayerSyncManager** | Менеджер синхронизации слоев между DXF структурой и QGIS canvas | Manager |
| **ZoomableGraphicsView** | Qt Graphics View с поддержкой масштабирования и навигации | Component |
| **PreviewDialog** | Диалог с предпросмотром SVG файлов в масштабируемом представлении | Dialog |

---

## 3. Диаграммы последовательности

### 3.1 Нормальный ход: Выбор сущности в дереве

```plantuml
@startuml widgets_normal_flow

actor User
participant "SelectableDxfTreeHandler" as Handler
participant "QTreeWidget" as Tree
participant "SelectEntityUseCase" as UseCase
database "Domain"

User -> Tree: Нажать чекбокс элемента
Tree -> Handler: itemChanged(item, column)
activate Handler

Handler -> Handler: _get_dto_for_item(item)
return DXFEntityDTO

Handler -> UseCase: execute_single(entity_id, is_selected=True)
activate UseCase

UseCase -> Domain: обновить состояние сущности
Domain -> Domain: entity.is_selected = True
return AppResult<void>

return is_success

Handler -> Handler: _update_tree_ui()
Handler -> Tree: update()
deactivate Handler

@enduml
```

### 3.2 Альтернативный нормальный ход: Открытие предпросмотра

```plantuml
@startuml widgets_alt_normal_flow

actor User
participant "PreviewDialog" as Dialog
participant "ZoomableGraphicsView" as View
participant "QGraphicsScene" as Scene

User -> Dialog: Нажать кнопку "Preview"
activate Dialog

Dialog -> Dialog: create_instructions()
Dialog -> Dialog: setup_ui(svg_path)

Dialog -> View: создать экземпляр
activate View

View -> Scene: создать QGraphicsScene
View -> View: setRenderHints()
return ZoomableGraphicsView

Dialog -> Dialog: fitInView(scene.sceneRect)
return PreviewDialog

User -> View: Крутить колесик мыши + Ctrl
View -> View: wheelEvent(event)
View -> View: scale(factor, factor)

User -> View: Дважды кликнуть ЛКМ
View -> View: mouseDoubleClickEvent(event)
View -> View: resetView()

@enduml
```

### 3.3 Сценарий прерывания пользователем: Закрытие документа

```plantuml
@startuml widgets_user_interruption

actor User
participant "SelectableDxfTreeHandler" as Handler
participant "QPushButton (Remove)" as Button
participant "CloseDocumentUseCase" as UseCase
database "Domain"

User -> Button: Нажать кнопку удаления
Button -> Handler: _on_remove_button_click(item)
activate Handler

Handler -> Handler: _get_dto_for_item(item)
return DXFDocumentDTO

Handler -> UseCase: execute(document_id)
activate UseCase

UseCase -> Domain: закрыть документ
Domain -> Domain: document.is_open = False
Domain -> Domain: clear_layers()
return AppResult<void>

alt result.is_fail
    Handler -> Handler: _logger.error()
else result.is_success
    Handler -> Handler: _item_to_dto.remove(item)
    Handler -> Handler: _update_tree_ui()
end

deactivate UseCase
deactivate Handler

@enduml
```

### 3.4 Сценарий системного прерывания: Ошибка синхронизации слоев

```plantuml
@startuml widgets_system_interruption

participant "QGISLayerSyncManager" as Manager
participant "QgsProject" as QGIS
participant "ExportService" as Service
participant "Logger" as Log

activate Manager
Manager -> QGIS: add_layer(layer_name, geometries)

alt QGIS ошибка: слой с таким именем существует
    QGIS -> QGIS: raise QgsLayerTreeError
    Manager -> Log: logger.error("Layer already exists")
else QGIS успех: слой добавлен
    QGIS -> Manager: return QgsVectorLayer
    Manager -> Manager: layer_map[layer_name] = layer
end

Manager -> QGIS: refresh canvas
deactivate Manager

@enduml
```

---

## 4. Уточненная диаграмма классов (с типами связей)

```plantuml
@startuml presentation_widgets_refined

package "presentation.widgets" {
    class SelectableDxfTreeHandler {
        - tree_widget
        - item_to_dto
        - close_doc_use_case
        - select_entity_use_case
        + update_tree()
        + clear_tree()
    }
    
    class ViewerDxfTreeHandler {
        - tree_widget
        - item_to_dto
        - active_doc_service
        + update_tree()
        + clear_tree()
    }
    
    class QGISLayerSyncManager {
        - canvas
        - layer_map
        - active_doc_service
        + add_layer()
        + remove_layer()
        + sync_selection()
    }
    
    class ZoomableGraphicsView {
        - zoom_factor
        + wheelEvent()
        + resetView()
    }
    
    class PreviewDialog {
        - svg_path
        - view
        + setup_ui()
    }
}

package "application.use_cases" {
    class SelectEntityUseCase
    class CloseDocumentUseCase
}

package "application.services" {
    class ActiveDocumentService
}

package "application.interfaces" {
    interface ILocalization
    interface ILogger
}

SelectableDxfTreeHandler --> SelectEntityUseCase: uses
SelectableDxfTreeHandler --> CloseDocumentUseCase: uses
ViewerDxfTreeHandler --> ActiveDocumentService: uses
QGISLayerSyncManager --> ActiveDocumentService: uses
PreviewDialog *-- ZoomableGraphicsView: contains

SelectableDxfTreeHandler -.-> ILocalization: depends
SelectableDxfTreeHandler -.-> ILogger: depends

@enduml
```

---

## 5. Детальная диаграмма классов (со всеми полями и методами)

```plantuml
@startuml presentation_widgets_detailed

package "presentation.widgets" {
    
    class SelectableDxfTreeHandler {
        - _tree_widget: QTreeWidget
        - _item_to_dto: list[tuple[QTreeWidgetItem, DXFBaseDTO]]
        - _close_doc_use_case: CloseDocumentUseCase
        - _select_entity_use_case: SelectEntityUseCase
        - _active_doc_service: ActiveDocumentService
        - _localization: ILocalization
        - _logger: ILogger
        --
        + __init__(tree_widget, ...use_cases)
        + update_tree(document: DXFDocumentDTO)
        + clear_tree()
        + _get_dto_for_item(item: QTreeWidgetItem): DXFBaseDTO | None
        + _add_dto_tree_item(parent: QTreeWidgetItem, dto: DXFBaseDTO)
        + _add_remove_button_to_item(item: QTreeWidgetItem)
        + _on_item_check_changed(item: QTreeWidgetItem, column: int)
        + _on_remove_button_click(item: QTreeWidgetItem)
    }
    
    class ViewerDxfTreeHandler {
        - _tree_widget: QTreeWidget
        - _item_to_dto: list[tuple[QTreeWidgetItem, DXFBaseDTO]]
        - _active_doc_service: ActiveDocumentService
        - _localization: ILocalization
        - _logger: ILogger
        --
        + __init__(tree_widget, ...services)
        + update_tree(document: DXFDocumentDTO)
        + clear_tree()
        + highlight_entity(entity_id: int)
        + unhighlight_all()
        + _get_dto_for_item(item: QTreeWidgetItem): DXFBaseDTO | None
        + _add_dto_tree_item(parent: QTreeWidgetItem, dto: DXFBaseDTO)
        + _on_item_double_click(item: QTreeWidgetItem)
        + _apply_highlight_style(item: QTreeWidgetItem)
    }
    
    class QGISLayerSyncManager {
        - _canvas: QgsMapCanvas
        - _layer_map: dict[str, QgsVectorLayer]
        - _active_doc_service: ActiveDocumentService
        - _export_service: ExportService
        - _logger: ILogger
        --
        + __init__(canvas: QgsMapCanvas, ...services)
        + add_layer(layer_name: str, layer_dto: DXFLayerDTO)
        + remove_layer(layer_name: str)
        + remove_all_layers()
        + sync_selection(selected_ids: set[int])
        + get_layer(layer_name: str): QgsVectorLayer | None
        + _on_selection_changed()
        + _create_qgis_layer(layer_dto: DXFLayerDTO): QgsVectorLayer
        + _export_to_qgis(entities: list[DXFEntityDTO])
    }
    
    class ZoomableGraphicsView {
        - zoom_factor: float
        - _scene: QGraphicsScene
        --
        + __init__(parent: QWidget | None = None)
        + wheelEvent(event: QWheelEvent)
        + mouseDoubleClickEvent(event: QMouseEvent)
        + resetView()
        + setScene(scene: QGraphicsScene)
        + scale(sx: float, sy: float)
    }
    
    class PreviewDialog {
        - _svg_path: str
        - view: ZoomableGraphicsView
        - lm: LocalizationManager
        --
        + __init__(svg_path: str, parent: QWidget | None = None)
        + setup_ui(svg_path: str)
        + create_instructions(): QLabel
        + create_control_buttons(): QWidget
        + setup_svg_view(svg_path: str)
        + reset_view()
        + _on_zoom_in()
        + _on_zoom_out()
        + _on_reset_view()
    }
}

@enduml
```

---

## 6. Таблицы описания полей и методов

### 6.1 SelectableDxfTreeHandler

#### Поля

| Название | Тип | Модификатор | Описание |
|----------|-----|-------------|---------|
| `_tree_widget` | QTreeWidget | private | виджет дерева для отображения структуры DXF |
| `_item_to_dto` | list[tuple] | private | отображение элементов дерева на DTO сущностей |
| `_close_doc_use_case` | CloseDocumentUseCase | private | use case для закрытия документов |
| `_select_entity_use_case` | SelectEntityUseCase | private | use case для выбора сущностей |
| `_active_doc_service` | ActiveDocumentService | private | сервис активного документа |
| `_localization` | ILocalization | private | локализация интерфейса |
| `_logger` | ILogger | private | логирование ошибок и событий |

#### Методы

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| `__init__()` | tree_widget, use_cases, services | void | инициализирует обработчик дерева |
| `update_tree()` | document: DXFDocumentDTO | void | обновляет дерево с новыми данными |
| `clear_tree()` | - | void | очищает дерево от всех элементов |
| `_get_dto_for_item()` | item: QTreeWidgetItem | DXFBaseDTO \| None | находит DTO для элемента |
| `_add_dto_tree_item()` | parent: QTreeWidgetItem, dto: DXFBaseDTO | void | добавляет элемент в дерево |
| `_add_remove_button_to_item()` | item: QTreeWidgetItem | void | добавляет кнопку удаления |
| `_on_item_check_changed()` | item, column | void | обработчик изменения чекбокса |
| `_on_remove_button_click()` | item: QTreeWidgetItem | void | обработчик нажатия кнопки удаления |

### 6.2 ViewerDxfTreeHandler

#### Поля

| Название | Тип | Модификатор | Описание |
|----------|-----|-------------|---------|
| `_tree_widget` | QTreeWidget | private | виджет дерева для отображения |
| `_item_to_dto` | list[tuple] | private | сопоставление элементов и DTO |
| `_active_doc_service` | ActiveDocumentService | private | сервис активного документа |
| `_localization` | ILocalization | private | локализация |
| `_logger` | ILogger | private | логирование |
| `_highlighted_item` | QTreeWidgetItem \| None | private | текущий выделенный элемент |

#### Методы

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| `__init__()` | tree_widget, services | void | инициализирует в режиме просмотра |
| `update_tree()` | document: DXFDocumentDTO | void | обновляет дерево |
| `clear_tree()` | - | void | очищает дерево |
| `highlight_entity()` | entity_id: int | void | выделяет сущность в дереве |
| `unhighlight_all()` | - | void | убирает подсветку со всех |
| `_on_item_double_click()` | item: QTreeWidgetItem | void | двойной клик по элементу |
| `_apply_highlight_style()` | item: QTreeWidgetItem | void | применяет стиль подсветки |

### 6.3 QGISLayerSyncManager

#### Поля

| Название | Тип | Модификатор | Описание |
|----------|-----|-------------|---------|
| `_canvas` | QgsMapCanvas | private | canvas для отображения слоев QGIS |
| `_layer_map` | dict[str, QgsVectorLayer] | private | слои по имени слоя |
| `_active_doc_service` | ActiveDocumentService | private | сервис активного документа |
| `_export_service` | ExportService | private | экспорт в QGIS |
| `_logger` | ILogger | private | логирование |

#### Методы

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| `__init__()` | canvas, services | void | инициализирует менеджер синхронизации |
| `add_layer()` | layer_name, layer_dto | void | добавляет слой в QGIS |
| `remove_layer()` | layer_name: str | void | удаляет слой из QGIS |
| `remove_all_layers()` | - | void | удаляет все слои синхронизации |
| `sync_selection()` | selected_ids: set \| None | void | синхронизирует выбранные сущности |
| `get_layer()` | layer_name: str | QgsVectorLayer \| None | получает слой по имени |
| `_on_selection_changed()` | - | void | обработчик изменения выбора |
| `_create_qgis_layer()` | layer_dto | QgsVectorLayer | создает слой QGIS |

### 6.4 ZoomableGraphicsView

#### Поля

| Название | Тип | Модификатор | Описание |
|----------|-----|-------------|---------|
| `zoom_factor` | float | public | множитель масштабирования при скролле |
| `_scene` | QGraphicsScene | private | сцена для отражения содержимого |

#### Методы

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| `__init__()` | parent: QWidget \| None | void | инициализирует представление |
| `wheelEvent()` | event: QWheelEvent | void | обрабатывает скролл для масштабирования |
| `mouseDoubleClickEvent()` | event: QMouseEvent | void | двойной клик сбрасывает вид |
| `resetView()` | - | void | сбрасывает масштаб и позицию |
| `setScene()` | scene: QGraphicsScene | void | устанавливает сцену |
| `scale()` | sx, sy: float | void | масштабирует содержимое |

### 6.5 PreviewDialog

#### Поля

| Название | Тип | Модификатор | Описание |
|----------|-----|-------------|---------|
| `_svg_path` | str | private | путь к SVG файлу |
| `view` | ZoomableGraphicsView | public | масштабируемое представление |
| `lm` | LocalizationManager | private | менеджер локализации |

#### Методы

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| `__init__()` | svg_path, parent | void | инициализирует диалог предпросмотра |
| `setup_ui()` | svg_path: str | void | настраивает пользовательский интерфейс |
| `create_instructions()` | - | QLabel | создает метку с инструкциями |
| `create_control_buttons()` | - | QWidget | создает панель кнопок управления |
| `setup_svg_view()` | svg_path: str | void | загружает и отображает SVG |
| `reset_view()` | - | void | сбрасывает вид в исходное состояние |
| `_on_zoom_in()` | - | void | увеличить масштаб |
| `_on_zoom_out()` | - | void | уменьшить масштаб |
| `_on_reset_view()` | - | void | сбросить вид |

---

## 7. Взаимодействие с другими пакетами

### Входящие зависимости (другие пакеты используют widgets)

- **presentation/dialogs** → SelectableDxfTreeHandler, ViewerDxfTreeHandler
  - Диалоги используют обработчики дерева для отображения структур

- **presentation/services** (если есть) → QGISLayerSyncManager, PreviewDialog
  - Сервисы управляют синхронизацией слоев

### Исходящие зависимости (widgets использует)

- **application/use_cases** (SelectEntityUseCase, CloseDocumentUseCase)
  - Обработчики дерева делегируют бизнес-логику
  
- **application/services** (ActiveDocumentService)
  - Получение текущего документа и его состояния
  
- **application/interfaces** (ILocalization, ILogger)
  - Локализация текстов и логирование

- **application/dtos** (DXFDocumentDTO, DXFLayerDTO, DXFEntityDTO)
  - Работа со структурированными данными

- **infrastructure/qgis** (QgsMapCanvas, QgsVectorLayer)
  - QGIS интеграция для отображения и синхронизации

---

## 8. Правила и ограничения пакета

### Архитектурные правила

1. **Слой**: widgets представляет **Presentation Layer** на архитектурной диаграмме
2. **Зависимости**: только ВНИЗ (к Application и Domain слоям)
3. **Инъекция**: использует `@inject.autoparams()` для внедрения зависимостей
4. **Интерфейсы**: работает через интерфейсы (ILocalization, ILogger, ISettings)

### Паттерны проектирования

- **Handler Pattern**: SelectableDxfTreeHandler, ViewerDxfTreeHandler
  - инкапсулируют логику работы с QTreeWidget
  
- **Manager Pattern**: QGISLayerSyncManager
  - управляет состоянием слоев и синхронизацией
  
- **Component Pattern**: ZoomableGraphicsView, PreviewDialog
  - переиспользуемые UI компоненты

### Правила кодирования

1. Все сигналы/слоты PyQt5 документированы
2. Обработке ошибок - логирование через ILogger
3. Локализация - через ILocalization.tr()
4. Тред-безопасность: SelectableDxfTreeHandler использует QSignalBlocker
5. Ленивая загрузка элементов дерева при большом объеме данных

---

## 9. Состояние проектирования

✅ **Завершено**: все классы описаны, диаграммы созданы, методы задокументированы.

**Готово к использованию в диплому**: полная документация архитектуры виджетов и их взаимодействия с бизнес-логикой приложения.
