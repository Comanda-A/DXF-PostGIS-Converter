# Проектирование пакета services (domain)

**Пакет**: `domain/services`

**Назначение**: Бизнес-логика сервисов предметной области независимо от реализации, содержит главные операции над доменными объектами.

**Расположение**: `src/domain/services/`

---

## 1. Исходная диаграмма классов

```plantuml
@startuml domain_services_original

package "domain.services" {
    
    class DocumentService {
        + create_document(name: str): DXFDocument
        + validate_document(doc: DXFDocument): bool
        + get_document_info(doc: DXFDocument): dict
        + merge_documents(doc1: DXFDocument, doc2: DXFDocument): DXFDocument
    }
    
    class LayerService {
        + create_layer(name: str, document: DXFDocument): DXFLayer
        + validate_layer(layer: DXFLayer): bool
        + compute_layer_bounds(layer: DXFLayer): Bounds
        + get_layer_statistics(layer: DXFLayer): dict
    }
    
    class EntityService {
        + create_entity(entity_type: str, geometry): DXFEntity
        + validate_entity(entity: DXFEntity): bool
        + compute_entity_properties(entity: DXFEntity): dict
        + get_entity_relationships(entity: DXFEntity): list[str]
    }
    
    class SelectionService {
        + select_entity(entity: DXFEntity)
        + deselect_entity(entity: DXFEntity)
        + clear_selection()
        + get_selected_entities(): list[DXFEntity]
    }
    
    DocumentService -.-> DXFDocument
    LayerService -.-> DXFLayer
    EntityService -.-> DXFEntity
    SelectionService -.-> DXFEntity
}

package "domain.entities" {
    class DXFDocument
    class DXFLayer
    class DXFEntity
}

@enduml
```

---

## 2. Таблица описания классов

| Класс | Назначение | Тип |
|-------|-----------|-----|
| **DocumentService** | Операции над документами (создание, валидация, слияние) | Service |
| **LayerService** | Операции над слоями (создание, границы, статистика) | Service |
| **EntityService** | Операции над сущностями (создание, валидация, свойства) | Service |
| **SelectionService** | Управление выбранными сущностями | Service |

---

## 3. Четыре диаграммы последовательности

### 3.1 Нормальный ход: Создание документа с валидацией

```plantuml
@startuml domain_services_normal

participant "UseCase" as UC
participant "DocumentService" as DS
participant "Validation" as Val
participant "DXFDocument" as Doc

UC -> DS: create_document("Project1")
activate DS

DS -> Doc: new DXFDocument(name="Project1")
DS -> DS: set defaults
return DXFDocument

DS -> Val: validate_document(doc)
activate Val
Val -> Val: check name not empty
Val -> Val: check structure valid
return bool (True)

DS -> UC: return DXFDocument

@enduml
```

### 3.2 Альтернативный ход: Слияние двух документов

```plantuml
@startuml domain_services_alt

participant "ExportUseCase" as UC
participant "DocumentService" as DS
participant "LayerService" as LS
participant "MergedDoc" as Doc

UC -> DS: merge_documents(doc1, doc2)
activate DS

DS -> DS: get layers from doc1
DS -> LS: for each layer in doc2
activate LS
LS -> LS: deep_copy layer
return copied_layer
DS -> DS: add_layer_to_merged(copied)

DS -> Doc: create merged document
return DXFDocument

@enduml
```

### 3.3 Прерывание: Невалидная сущность

```plantuml
@startuml domain_services_interruption

participant "EntityService" as ES
participant "Validator" as Val

ES -> Val: validate_entity(invalid_entity)
activate Val

Val -> Val: check coordinates
alt Координаты вне диапазона
    Val -x ES: raise ValidationError
else OK
    return True
end

@enduml
```

### 3.4 Системное прерывание: Ошибка в валидации

```plantuml
@startuml domain_services_system

participant "DocumentService" as DS
participant "Validator" as Val

DS -> Val: validate_document(corrupted_doc)

alt Структура повреждена
    Val -x DS: raise StructureError
else Success
    Val -> DS: return True
end

@enduml
```

---

## 4. Уточненная диаграмма классов

```plantuml
@startuml domain_services_refined

package "domain.services" {
    class DocumentService {
        + create_document(name): DXFDocument
        + validate_document(): bool
        + merge_documents(): DXFDocument
    }
    
    class LayerService {
        + create_layer(name, doc): DXFLayer
        + compute_layer_bounds(): Bounds
    }
    
    class EntityService {
        + create_entity(type): DXFEntity
        + validate_entity(): bool
    }
    
    class SelectionService {
        - selected: set[DXFEntity]
        + select_entity(entity): void
        + get_selected_entities(): list
    }
}

DocumentService --> DXFDocument: operates on
LayerService --> DXFLayer: operates on
EntityService --> DXFEntity: operates on

@enduml
```

---

## 5. Детальная диаграмма классов

```plantuml
@startuml domain_services_detailed

package "domain.services" {
    
    class DocumentService {
        - _logger: ILogger
        --
        + create_document(name: str): DXFDocument
        + validate_document(doc: DXFDocument): bool
        + get_document_info(doc: DXFDocument): dict
        + merge_documents(doc1, doc2): DXFDocument
        - _validate_document_structure(doc): bool
        - _validate_document_data(doc): bool
    }
    
    class LayerService {
        - _logger: ILogger
        --
        + create_layer(name: str, doc: DXFDocument): DXFLayer
        + validate_layer(layer: DXFLayer): bool
        + compute_layer_bounds(layer: DXFLayer): Bounds
        + get_layer_statistics(layer: DXFLayer): dict
        - _calculate_centroid(entities): tuple
    }
    
    class EntityService {
        - _logger: ILogger
        --
        + create_entity(entity_type: str, geometry): DXFEntity
        + validate_entity(entity: DXFEntity): bool
        + compute_entity_properties(entity: DXFEntity): dict
        + get_entity_relationships(entity: DXFEntity): list
        - _infer_entity_type(geometry): str
    }
    
    class SelectionService {
        - _selected_entities: set[DXFEntity]
        - _selection_history: list[set]
        - _logger: ILogger
        --
        + select_entity(entity: DXFEntity): None
        + deselect_entity(entity: DXFEntity): None
        + clear_selection(): None
        + get_selected_entities(): list[DXFEntity]
        + is_selected(entity: DXFEntity): bool
        + undo_selection(): None
    }
}

@enduml
```

---

## 6. Таблицы описания полей и методов

### DocumentService

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| `create_document()` | name: str | DXFDocument | создаёт новый документ |
| `validate_document()` | doc: DXFDocument | bool | проверяет структуру документа |
| `get_document_info()` | doc | dict | получает метаинформацию |
| `merge_documents()` | doc1, doc2 | DXFDocument | объединяет два документа |

### LayerService

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| `create_layer()` | name, doc | DXFLayer | создаёт слой в документе |
| `validate_layer()` | layer | bool | проверяет слой на ошибки |
| `compute_layer_bounds()` | layer | Bounds | вычисляет границы слоя |
| `get_layer_statistics()` | layer | dict | статистика (кол-во элементов и т.д.) |

### EntityService

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| `create_entity()` | type, geometry | DXFEntity | создаёт элемент |
| `validate_entity()` | entity | bool | проверяет элемент |
| `compute_entity_properties()` | entity | dict | вычисляет свойства (площадь и т.д.) |
| `get_entity_relationships()` | entity | list | связи с другими элементами |

### SelectionService

| Название | Параметры | Возвращает | Описание |
|----------|-----------|-----------|---------|
| `select_entity()` | entity | void | выбрать элемент |
| `deselect_entity()` | entity | void | отменить выбор |
| `clear_selection()` | - | void | очистить выбор |
| `get_selected_entities()` | - | list | получить выбранные |
| `is_selected()` | entity | bool | проверить выбран ли |
| `undo_selection()` | - | void | отменить последнее действие |

---

## 7. Состояние проектирования

✅ **Завершено**: полная документация domain/services слоя.
