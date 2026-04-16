# Проектирование пакета events (application)

**Пакет**: `application/events`

**Назначение**: Определение событий приложения и их обработчики для реактивного программирования.

---

## 1. Таблица описания классов

| Класс | Назначение | Тип |
|-------|-----------|-----|
| **IAppEvent** | Базовый интерфейс события | Interface |
| **DocumentOpenedEvent** | Событие открытия документа | Event |
| **DocumentClosedEvent** | Событие закрытия документа | Event |
| **SelectionChangedEvent** | Событие изменения выбора | Event |
| **ImportStartedEvent** | Событие начала импорта | Event |
| **ImportCompletedEvent** | Событие завершения импорта | Event |
| **ExportStartedEvent** | Событие начала экспорта | Event |
| **ExportCompletedEvent** | Событие завершения экспорта | Event |
| **IAppEventBus** | Шина событий для подписки и публикации | Interface |

---

## 2. Диаграмма классов

```plantuml
@startuml application_events

package "application.events" {
    
    interface IAppEvent {
        + get_type(): str
        + get_timestamp(): datetime
        + get_data(): dict
    }
    
    class DocumentOpenedEvent {
        - document_id: int
        - document_name: str
        - timestamp: datetime
        --
        + get_document_id(): int
        + get_document_name(): str
    }
    
    class SelectionChangedEvent {
        - selected_ids: set[int]
        - layer_id: int
        --
        + get_selected_ids(): set[int]
        + get_layer_id(): int
    }
    
    class ImportCompletedEvent {
        - document_id: int
        - entities_imported: int
        - duration: float
        --
        + get_count(): int
        + get_duration(): float
    }
    
    interface IAppEventBus {
        + subscribe(event_type: str, handler: Callable): int
        + unsubscribe(handler_id: int): bool
        + publish(event: IAppEvent): void
    }
    
    DocumentOpenedEvent --|> IAppEvent
    SelectionChangedEvent --|> IAppEvent
    ImportCompletedEvent --|> IAppEvent
}

@enduml
```

---

## 3. Описание событий

### DocumentOpenedEvent
- **Данные**: document_id, document_name
- **Когда**: при открытии DXF файла
- **Слушатели**: UI обновляет заголовок, становятся доступными кнопки

### SelectionChangedEvent
- **Данные**: selected_ids (множество выбранных ID), layer_id
- **Когда**: пользователь выбирает элемент в дереве или на карте
- **Слушатели**: UI обновляет подсветку, показывает свойства

### ImportCompletedEvent
- **Данные**: document_id, entities_imported (кол-во импортированных), duration
- **Когда**: завершен импорт из DXF
- **Слушатели**: UI показывает сообщение об успехе, обновляет прогресс

### ExportCompletedEvent
- **Данные**: file_path, entities_exported
- **Когда**: завершен экспорт в DXF
- **Слушатели**: UI показывает сообщение, может открыть папку

---

## 4. Интерфейс IAppEventBus

```python
# Пример использования
event_bus.subscribe("document_opened", on_document_opened)
event_bus.subscribe("selection_changed", on_selection_changed)

# Публикация события
event = DocumentOpenedEvent(doc_id=123, doc_name="Project1")
event_bus.publish(event)
```

**Статус**: ✅ Завершено
