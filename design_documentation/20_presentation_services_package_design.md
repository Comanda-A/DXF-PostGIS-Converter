# Проектирование пакета services (presentation)

**Пакет**: `presentation/services`

**Назначение**: Сервисы presentation слоя для управления состоянием UI и взаимодействию между диалогами/виджетами.

---

## 1. Таблица описания классов

| Класс | Назначение | Методы |
|-------|-----------|--------|
| **DialogService** | Управление жизненным циклом диалогов | show, hide, close, is_open |
| **StateService** | Управление глобальным состоянием UI | set_state, get_state, subscribe |
| **NotificationService** | Показ уведомлений и сообщений | show_info, show_warning, show_error |
| **ProgressService** | Управление прогрессом операций | start_progress, update_progress, finish_progress |
| **ThemeService** | Управление темой оформления | set_theme, get_theme, get_available_themes |

---

## 2. Диаграмма классов

```plantuml
@startuml presentation_services

package "presentation.services" {
    
    class DialogService {
        - _dialogs: dict[str, QDialog]
        - _logger: ILogger
        --
        + show_dialog(dialog_name: str): void
        + hide_dialog(dialog_name: str): void
        + close_dialog(dialog_name: str): void
        + is_dialog_open(dialog_name: str): bool
        + register_dialog(name: str, dialog: QDialog): void
    }
    
    class StateService {
        - _state: dict[str, Any]
        - _observers: dict[str, list[Callable]]
        --
        + set_state(key: str, value: Any): void
        + get_state(key: str, default: Any): Any
        + subscribe(key: str, callback: Callable): int
        + unsubscribe(callback_id: int): void
    }
    
    class NotificationService {
        - _logger: ILogger
        --
        + show_info(title: str, message: str): void
        + show_warning(title: str, message: str): void
        + show_error(title: str, message: str): void
        + show_question(title: str, message: str): bool
    }
    
    class ProgressService {
        - _dialogs: dict[int, QProgressDialog]
        --
        + start_progress(task_id: int, title: str, max_value: int): void
        + update_progress(task_id: int, current: int): void
        + finish_progress(task_id: int): void
    }
    
    class ThemeService {
        - _current_theme: str
        - _themes: dict[str, str]
        - _settings: ISettings
        --
        + set_theme(theme_name: str): void
        + get_theme(): str
        + get_available_themes(): list[str]
    }
}

@enduml
```

---

## 3. Использование

### DialogService
```python
# Регистрация диалога при инициализации
dialog_service.register_dialog("import_dialog", ImportDialog())

# Показ диалога
dialog_service.show_dialog("import_dialog")
```

### StateService
```python
# Установка состояния
state_service.set_state("selected_layer_id", 42)

# Подписка на изменение состояния
state_service.subscribe("selected_layer_id", on_layer_changed)
```

### NotificationService
```python
# Показ уведомления
notification_service.show_info("Import", "Successfully imported 100 entities")

# Диалог вопроса
if notification_service.show_question("Delete", "Delete this layer?"):
    # пользователь подтвердил
    pass
```

### ProgressService
```python
# Начало операции с прогрессом
progress_service.start_progress(task_id=1, title="Importing...", max_value=100)

# Обновление прогресса
for i in range(100):
    progress_service.update_progress(task_id=1, current=i)

# Завершение
progress_service.finish_progress(task_id=1)
```

### ThemeService
```python
# Смена темы
theme_service.set_theme("dark")

# Получение доступных тем
themes = theme_service.get_available_themes()
```

---

## 4. Архитектурные причины

✅ **Разделение ответственности** — различные аспекты UI управления отделены
✅ **Переиспользуемость** — сервисы используют несколько диалогов/виджетов
✅ **Тестируемость** — легко мокировать сервисы в юнит тестах
✅ **Слабая связанность** — диалоги не знают друг о друге, общаются через сервисы

**Статус**: ✅ Завершено
