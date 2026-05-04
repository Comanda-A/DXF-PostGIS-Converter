# 5.2.11. Проектирование классов пакета «qgis»

Пакет «qgis» реализует инфраструктурную интеграцию с QGIS API: логирование, настройки, событийную шину и чтение конфигураций подключений.

## 5.2.11.1. Исходная диаграмма классов

Диаграмма содержит только классы пакета `infrastructure/qgis`.

```mermaid
graph LR
     Logger
     Settings
     QtEvent
     QtSignalHolder
     QtAppEvents
     QgisConnectionProvider

    QtAppEvents -.->|"создает"| QtEvent 
    QtEvent -.-> |"создает"|QtSignalHolder 
    QgisConnectionProvider -->|"использует"| Logger 
    Logger -->|"использует"| Settings
```

### Таблица 1. Описание классов пакета «qgis»

| Класс | Описание |
|---|---|
| Logger | Запись сообщений в `QgsMessageLog`, управление флагом enabled |
| Settings | Адаптер над `QgsSettings` |
| QtEvent | Обертка над Qt-сигналом с connect/disconnect/emit/clear |
| QtSignalHolder | Внутренний QObject с `pyqtSignal(object)` |
| QtAppEvents | Контейнер доменных событий приложения на базе `QtEvent` |
| QgisConnectionProvider | Получение PostgreSQL подключений из `QSettings` QGIS |

## 5.2.11.2. Диаграмма последовательностей взаимодействия объектов классов

На одной диаграмме показано взаимодействие всех классов пакета. Первый блок намеренно без названия и используется как общий инициатор сценариев. Внешние объекты QGIS на диаграмме не отображаются.

```mermaid
sequenceDiagram
    participant Entry as ""
    participant Cfg as Settings
    participant Log as Logger
    participant Provider as QgisConnectionProvider
    participant Events as QtAppEvents
    participant EventObj as QtEvent
    participant Holder as QtSignalHolder

    alt Нормальный сценарий
        Entry->>Cfg: Сценарий: нормальный ход
        activate Cfg
        Cfg-->>Entry: logger_enabled
        deactivate Cfg

        Entry->>Log: set_enabled(logger_enabled)
        activate Log
        Log->>Cfg: set_value("Logger", enabled)
        Cfg-->>Log: ok
        deactivate Log

        Entry->>Provider: Сценарий: нормальный ход
        activate Provider
        Provider->>Log: message("Loaded QGIS connection")
        Provider-->>Entry: list[ConnectionConfigDTO]
        deactivate Provider

        Entry->>Holder: Сценарий: нормальный ход
        Holder-->>Entry: holder ready

        Entry->>Events: Сценарий: нормальный ход
        activate Events
        Events->>EventObj: on_document_opened()
        Events-->>Entry: event channel
        deactivate Events

        Entry->>EventObj: connect(handler)
        activate EventObj
        EventObj->>Holder: signal connect
        Holder-->>EventObj: connected

        Entry->>EventObj: emit(data)
        EventObj->>Holder: signal emit
        Holder-->>EventObj: delivered
        EventObj->>Holder: clear subscriptions
        deactivate EventObj

    else Системное прерывание
        Entry->>Provider: Сценарий: прерывание системой
        activate Provider
        Provider--xProvider: internal exception while reading settings
        Provider->>Log: error("Error reading PostgreSQL connections")
        
        Provider-->>Entry: empty list
        deactivate Provider
        activate Log
        Log->>Cfg: set_value("ErrorState", critical)
        deactivate Log

        Entry->>Events: Сценарий: экстренное завершение
        activate Events
        Events->>EventObj: on_document_opened()
        activate EventObj
        EventObj->>Holder: disconnect all
        Holder-->>EventObj: emergency cleared
        deactivate EventObj
        
        Events->>EventObj: on_document_saved()
        activate EventObj
        EventObj->>Holder: disconnect all
        Holder-->>EventObj: emergency cleared
        deactivate EventObj
        
        Events->>EventObj: on_document_closed()
        activate EventObj
        EventObj->>Holder: disconnect all
        Holder-->>EventObj: emergency cleared
        deactivate EventObj
        
        Events->>EventObj: on_document_modified()
        activate EventObj
        EventObj->>Holder: disconnect all
        Holder-->>EventObj: emergency cleared
        deactivate EventObj
        
        Events-->>Entry: all event channels cleaned
        deactivate Events

        Entry->>Log: error("System emergency shutdown completed")
        activate Log
        Log->>Cfg: set_value("SystemReady", False)
        Log-->>Entry: emergency logged
        deactivate Log

    else Прерывание пользователем
        Entry->>Log: Сценарий: прерывание пользователем
        activate Log
        Log->>Cfg: set_value("Logger", False)
        Log-->>Entry: logging disabled
        deactivate Log

        Entry->>EventObj: clear()
        activate EventObj
        EventObj->>Holder: disconnect all
        Holder-->>EventObj: cleared
        EventObj-->>Entry: notifications stopped
        deactivate EventObj
    end
```

```mermaid
sequenceDiagram
    participant Entry as 
    participant Cfg as Settings
    participant Log as Logger
    participant Provider as QgisConnectionProvider
    participant Events as QtAppEvents
    participant EventObj as QtEvent
    participant Holder as QtSignalHolder

        Entry->>Cfg: set_value(...)
        activate Cfg
        Cfg-->>Entry: logger_enabled
        deactivate Cfg

        Entry->>Log: set_enabled(logger_enabled)
        activate Log
        Log->>Cfg: set_value("Logger", enabled)
        Cfg-->>Log: ok
        deactivate Log

        Entry->>Provider: _get_postgres_connections(...)
        activate Provider
        Provider->>Log: message("Loaded QGIS connection")
        Provider-->>Entry: list[ConnectionConfigDTO]
        deactivate Provider

        Entry->>Holder: connect(...)
        Holder-->>Entry: holder ready

        Entry->>Events: get_file(...)
        activate Events
        Events->>EventObj: on_document_opened()
        Events-->>Entry: event channel
        deactivate Events

        Entry->>EventObj: connect(handler)
        activate EventObj
        EventObj->>Holder: signal connect
        Holder-->>EventObj: connected

        Entry->>EventObj: emit(data)
        EventObj->>Holder: signal emit
        Holder-->>EventObj: delivered
        EventObj->>Holder: clear subscriptions
        deactivate EventObj

```

```mermaid
sequenceDiagram
    participant Entry as ""
    participant Cfg as Settings
    participant Log as Logger
    participant Provider as QgisConnectionProvider
    participant Events as QtAppEvents
    participant EventObj as QtEvent
    participant Holder as QtSignalHolder

        Entry->>Provider: _get_postgres_connections(...)
        activate Provider
        Provider--xProvider: internal exception while reading settings
        Provider->>Log: error("Error reading PostgreSQL connections")
        
        Provider-->>Entry: empty list
        deactivate Provider
        activate Log
        Log->>Cfg: set_value("ErrorState", critical)
        deactivate Log

        Entry->>Events: Сценарий: экстренное завершение
        activate Events
        Events->>EventObj: on_document_opened()
        activate EventObj
        EventObj->>Holder: disconnect all
        Holder-->>EventObj: emergency cleared
        deactivate EventObj
        
        Events->>EventObj: on_document_saved()
        activate EventObj
        EventObj->>Holder: disconnect all
        Holder-->>EventObj: emergency cleared
        deactivate EventObj
        
        Events->>EventObj: on_document_closed()
        activate EventObj
        EventObj->>Holder: disconnect all
        Holder-->>EventObj: emergency cleared
        deactivate EventObj
        
        Events->>EventObj: on_document_modified()
        activate EventObj
        EventObj->>Holder: disconnect all
        Holder-->>EventObj: emergency cleared
        deactivate EventObj
        
        Events-->>Entry: all event channels cleaned
        deactivate Events

        Entry->>Log: error("System emergency shutdown completed")
        activate Log
        Log->>Cfg: set_value("SystemReady", False)
        Log-->>Entry: emergency logged
        deactivate Log


```

## 5.2.11.3. Уточненная диаграмма классов

```mermaid
---
config:
    layout: elk
---
classDiagram
    class Logger
    class Settings
    class QtEvent
    class QtSignalHolder
    class QtAppEvents
    class QgisConnectionProvider

    QtAppEvents *-- QtEvent : создает
    QtEvent *-- QtSignalHolder : создает
    QgisConnectionProvider o-- Logger : использует
    Logger o-- Settings : использует

```

## 5.2.11.4. Детальная диаграмма классов

```mermaid
classDiagram
    class Logger {
        -_LOGGER_KEY: str
        -_settings: ISettings
        -_enabled: bool
        +is_enabled() bool
        +set_enabled(enabled) None
        +message(message, tag) None
        +warning(message, tag) None
        +error(message, tag) None
    }

    class Settings {
        -_settings
        +get_value(key, default, value_type)
        +set_value(key, value) None
        +remove(key) None
    }

    class QtSignalHolder {
        +event
    }

    class QtEvent {
        -_signal_holder: QtSignalHolder
        +connect(receiver) None
        +disconnect(receiver) None
        +emit(data) None
        +clear() None
    }

    class QtAppEvents {
        -_on_document_opened: QtEvent
        -_on_document_saved: QtEvent
        -_on_document_closed: QtEvent
        -_on_document_modified: QtEvent
        +__init__()
        +on_document_opened()
        +on_document_saved()
        +on_document_closed()
        +on_document_modified()
    }

    class QgisConnectionProvider {
        -_logger
        +get_qgis_connections() list
        +get_qgis_connection_password(connection_name) optional
        -_get_postgres_connections() list
    }

    QtAppEvents *-- QtEvent : создает
    QtEvent *-- QtSignalHolder : создает
    QgisConnectionProvider o-- Logger : использует
    Logger o-- Settings : использует
```

### Таблица 2. Ключевые поля классов пакета «qgis»

| Класс | Поле | Описание |
|---|---|---|
| Logger | _settings | Доступ к persistent настройкам |
| Logger | _enabled | Флаг включенности логирования |
| Settings | _settings | Объект `QgsSettings` |
| QtEvent | _signal_holder | Держатель `pyqtSignal` |
| QtAppEvents | _on_document_* | Набор событий приложения |
| QgisConnectionProvider | _logger | Логирование чтения и ошибок |

### Таблица 3. Ключевые методы классов пакета «qgis»

| Класс | Метод | Назначение |
|---|---|---|
| Logger | set_enabled | Переключение логгера и запись состояния в Settings |
| Logger | message/warning/error | Вывод сообщений в QGIS log |
| Settings | get_value/set_value/remove | Работа с `QgsSettings` |
| QtEvent | connect/disconnect | Управление подписками |
| QtEvent | emit/clear | Публикация и очистка обработчиков |
| QtAppEvents | on_document_opened/... | Выдача каналов событий |
| QgisConnectionProvider | get_qgis_connections | Получение списка подключений |
| QgisConnectionProvider | get_qgis_connection_password | Получение пароля подключения |

## 5.2.11.5. Подробные таблицы полей и методов классов

### Класс Logger

#### Описание полей класса

| Название | Тип | Описание |
|---|---|---|
| _LOGGER_KEY | str | Ключ настройки, включающей/отключающей логирование |
| _settings | ISettings | Адаптер доступа к persistent-настройкам |
| _enabled | bool | Текущее состояние логирования |

#### Описание методов класса

| Название | Параметры | Возвращает | Описание |
|---|---|---|---|
| is_enabled | - | bool | Возвращает текущее состояние логирования |
| set_enabled | enabled: bool | None | Устанавливает флаг и сохраняет его в Settings |
| message | message: str, tag: str | None | Пишет информационное сообщение в журнал QGIS |
| warning | message: str, tag: str | None | Пишет предупреждение в журнал QGIS |
| error | message: str, tag: str | None | Пишет ошибку в журнал QGIS |

### Класс Settings

#### Описание полей класса

| Название | Тип | Описание |
|---|---|---|
| _settings | QgsSettings | Объект QGIS для хранения пользовательских параметров |

#### Описание методов класса

| Название | Параметры | Возвращает | Описание |
|---|---|---|---|
| get_value | key: str, default: Any, value_type: type | Any | Возвращает значение настройки с типизацией |
| set_value | key: str, value: Any | None | Сохраняет значение настройки |
| remove | key: str | None | Удаляет настройку |

### Класс QtSignalHolder

#### Описание полей класса

| Название | Тип | Описание |
|---|---|---|
| event | pyqtSignal(object) | Qt-сигнал для публикации событий с payload |

#### Описание методов класса

| Название | Параметры | Возвращает | Описание |
|---|---|---|---|
| Нет публичных методов | - | - | Класс используется как holder сигнала внутри QtEvent |

### Класс QtEvent

#### Описание полей класса

| Название | Тип | Описание |
|---|---|---|
| _signal_holder | QtSignalHolder | Владеет объектом Qt-сигнала |

#### Описание методов класса

| Название | Параметры | Возвращает | Описание |
|---|---|---|---|
| connect | receiver: Callable[[Any], None] | None | Подписывает обработчик на событие |
| disconnect | receiver: Callable[[Any], None] | None | Отписывает обработчик |
| emit | data: Any | None | Публикует событие подписчикам |
| clear | - | None | Очищает все подписки |

### Класс QtAppEvents

#### Описание полей класса

| Название | Тип | Описание |
|---|---|---|
| _on_document_opened | QtEvent | Канал события открытия документа |
| _on_document_saved | QtEvent | Канал события сохранения документа |
| _on_document_closed | QtEvent | Канал события закрытия документа |
| _on_document_modified | QtEvent | Канал события изменения документа |
| _on_language_changed | QtEvent | Канал события смены языка |

#### Описание методов класса

| Название | Параметры | Возвращает | Описание |
|---|---|---|---|
| on_document_opened | - | QtEvent | Возвращает канал открытия документа |
| on_document_saved | - | QtEvent | Возвращает канал сохранения документа |
| on_document_closed | - | QtEvent | Возвращает канал закрытия документа |
| on_document_modified | - | QtEvent | Возвращает канал изменения документа |
| on_language_changed | - | QtEvent | Возвращает канал смены языка |

### Класс QgisConnectionProvider

#### Описание полей класса

| Название | Тип | Описание |
|---|---|---|
| _logger | ILogger | Логгер операций чтения подключений и ошибок |

#### Описание методов класса

| Название | Параметры | Возвращает | Описание |
|---|---|---|---|
| _get_postgres_connections | - | list[ConnectionConfigDTO] | Читает и парсит подключения PostgreSQL из QSettings |
| get_qgis_connections | - | list[ConnectionConfigDTO] | Публичный API получения подключений |
| get_qgis_connection_password | connection_name: str | Optional[str] | Возвращает пароль выбранного подключения |
