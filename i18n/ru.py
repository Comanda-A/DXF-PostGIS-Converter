"""
Файл локализации для русского языка
"""

CONFIG = {
    "code": "ru",
    "name": "Русский"
}

# Строки для основного диалога
MAIN_DIALOG = {
    "dialog_title": "DXF-PostGIS Конвертер",
    "help_dialog_title": "Справка",

    "tab_dxf_to_db": "Импорт",
    "tab_db_to_dxf": "Экспорт",
    "tab_settings": "Настройки",

    "open_dxf_button": "Открыть DXF",
    "import_dxf_button": "Импорт в БД",
    "save_dxf_button": "Сохранить в файл..",
    "connection_editor_button": "Редактор подключений",
    "current_connection_label": "Текущее подключение:",
    "schema_label": "Схема файлов:",
    "refresh_db_button": "Обновить файлы",
    "export_db_button": "Экспортировать",
    "apply_filter_button": "Применить",
    "clear_filter_button": "Сбросить",
    "select_area_button": "Выбрать область на карте",

    "filter_group": "Фильтр выделения",
    "selection_group": "Область выбора",

    "file_label": "Файл:",
    "search_label": "Поиск:",
    "figure_label": "Тип фигуры:",
    "rule_label": "Правило выбора:",
    "mode_label": "Режим выделения:",
    "coord_label": "Координаты области:",
    "db_structure_label": "Структура баз данных:",
    "language_label": "Язык интерфейса:",
    "dxf_tree_label": "Структура DXF-файла:",

    "layer_search_edit": "Название слоя...",
    "coord_edit": "Выберите область на карте...",

    "shape_rectangle": "Прямоугольник",
    "shape_circle": "Круг",
    "shape_polygon": "Полигон",
    "selection_inside": "Внутри",
    "selection_outside": "Снаружи",
    "selection_intersect": "Пересечение",
    "mode_join": "Объединить",
    "mode_replace": "Заменить",
    "mode_subtract": "Вычесть",

    "logging_check": "Включить логирование операций",
    "db_files_empty": "Файлы не найдены",
    "select_files_to_export": "Выберите хотя бы один файл для экспорта.",
    "select_connection_first": "Сначала выберите подключение к базе данных.",
    "select_schema_first": "Сначала выберите схему с DXF-файлами.",
    "select_file_first": "Сначала выберите DXF-файл.",
    "choose_export_folder": "Выберите папку для экспорта",
    "save_as": "Сохранить как",
    "export_success_qgis": "Экспорт завершен. Файлов загружено в QGIS: {}",
    "export_success_folder": "Экспорт завершен. Файлы сохранены в: {}",
    "export_in_progress": "Выполняется экспорт...",
    "cancel": "Отмена"
}

IMPORT_DIALOG = {
    "dialog_title": "Импорт DXF в PostGIS",
    "help_dialog_title": "Справка по импорту",
    
    # Группы
    "dxf_files_group": "DXF-файлы",
    "database_connection_group": "Подключение к базе данных",
    "import_settings_group": "Настройки импорта",
    "layers_schema_group": "Параметры схемы слоев",
    "files_schema_group": "Параметры схемы файлов",
    
    # Кнопки подключения к БД
    "select_database_button": "Выбрать БД",
    "connect_button": "Подключиться",
    
    # Лейблы подключения к БД
    "address_label": "Адрес:",
    "port_label": "Порт:",
    "database_name_label": "Имя базы данных:",
    "username_label": "Имя пользователя:",
    "password_label": "Пароль:",
    
    # Настройки импорта
    "filename_label": "Название файла:",
    "import_mode_label": "Режим импортирования:",
    "layer_mapping_hint_label": "Все существующие объекты будут заменены новыми",
    
    # ComboBox режима импортирования
    "overwrite_layers": "Перезаписывать слои",
    "overwrite_objects": "Обновление с добавлением",
    "add_objects": "Только добавление",

    "overwrite_layers_hint": "Все импортируемые слои будут полностью перезаписаны",
    "overwrite_objects_hint": "Существующие объекты будут обновлены, новые - добавлены, остальные останутся без изменений",   # 
    "add_objects_hint": "Существующие объекты будут пропущены, новые - добавлены, остальные останутся без изменений",
    
    # Параметры схемы слоев
    "layers_schema_label": "Схема для слоев:",
    "create_layers_schema_button": "Создать новую схему",
    
    # Параметры схемы файлов
    "import_only_layers_check": "Импортировать только слои",
    "import_only_layers_hint_label": "Возможна потеря данных при экспортировании",
    "files_schema_label": "Схема для файлов:",
    "create_files_schema_button": "Создать новую схему",
    
    # Кнопки внизу
    "cancel_button": "Отмена",
    "import_button": "Импортировать"
}

CONNECTION_EDITOR_DIALOG = {
    "dialog_title": "Редактор подключений",
    "update_button": "Обновить",
    "add_button": "Добавить соединение",
    "select_button": "Выбрать",
    "error_title": "Ошибка",
    "info_title": "Информация",
    "load_connections_error": "Не удалось загрузить список подключений",
    "schemas_load_failed": "Не удалось получить схемы",
    "schemas_load_error": "Не удалось получить схемы базы данных",
    "no_schemas_available": "Нет доступных схем",
    "tables_load_failed": "Не удалось получить таблицы",
    "edit_action": "Редактировать",
    "delete_action": "Удалить",
    "delete_confirmation_title": "Подтверждение удаления",
    "delete_confirmation_message": "Вы уверены, что хотите удалить подключение '{}'?",
    "delete_error": "Не удалось удалить подключение '{}'",
    "select_connection_prompt": "Выберите подключение."
}

CONNECTION_DIALOG = {
    "dialog_title": "Новое подключение",
    "connection_group": "Информация о соединении",
    "dbms_label": "СУБД",
    "name_label": "Название соединения",
    "address_label": "Адрес",
    "port_label": "Порт",
    "database_label": "База данных",
    "username_label": "Пользователь",
    "password_label": "Пароль",
    "check_button": "Проверить соединение",
    "ok_button": "Ок",
    "cancel_button": "Отмена",

    "warning_title": "Предупреждение",
    "error_title": "Ошибка",
    "success_title": "Успех",
    "confirmation_title": "Подтверждение",
    
    "name_required": "Не заполнено имя подключения",
    "address_required": "Не заполнен адрес сервера",
    "port_required": "Не заполнен порт",
    "database_required": "Не заполнено имя базы данных",
    "username_required": "Не заполнено имя пользователя",
    
    "connection_successful": "Подключение успешно установлено",
    "connection_failed": "Не удалось установить подключение. {}",
    "connection_check_error": "Ошибка при проверке подключения. {}",
    
    "connection_exists": "Подключение с именем '{}' уже существует. Перезаписать?",
    "save_error": "Ошибка при сохранении подключения. {}"
}

TREE_WIDGET_HANDLER = {

    "file_text": "{} | выделено слоев: {}/{} | выделено сущностей: {}/{}",
    "layer_text": "{} | выделено сущностей: {}/{}",
    "preview_button": "Превью",
    "remove_button": "Закрыть"
}

DB_TREE_HANDLER = {
    "preview_button": "Превью",
    "info_button": "Инфо",
    "delete_button": "Удалить"
}

# Контент справки для диалогов
HELP_CONTENT = {
    "IMPORT_DIALOG": """
<h2>Руководство по диалогу импорта DXF в PostGIS</h2>

<h3>Что делает этот диалог</h3>
<p>Диалог импортирует выбранные DXF-файлы в PostgreSQL/PostGIS. При импорте файл в БД создается автоматически: формируется запись файла и соответствующие таблицы слоев/сущностей.</p>

<h3>Какая структура БД создается</h3>
<ul>
    <li><b>files (в files schema):</b> реестр документов DXF: <code>id</code>, <code>filename</code>, <code>upload_date</code>, <code>update_date</code>.</li>
    <li><b>layers (в files schema):</b> слои документа: <code>id</code>, <code>document_id</code>, <code>name</code>, <code>schema_name</code>, <code>table_name</code>.</li>
    <li><b>content (в files schema):</b> бинарное содержимое файла: <code>id</code>, <code>document_id</code>, <code>content (BYTEA)</code>.</li>
    <li><b>Таблица слоя (в layer schema):</b> для каждого слоя создается/используется отдельная таблица сущностей: <code>id</code>, <code>entity_type</code>, <code>name</code>, <code>geometry</code>, <code>attributes (JSONB)</code>, <code>geometries (JSONB)</code>, <code>extra_data (JSONB)</code>.</li>
</ul>

<h3>Сущности и связи (как в коде)</h3>
<table border="1" cellpadding="4" cellspacing="0">
    <tr><th>Сущность в коде</th><th>Где хранится</th><th>Связь</th></tr>
    <tr><td>DXFDocument</td><td>files</td><td>По <code>id</code>; имя файла уникально (<code>filename UNIQUE</code>)</td></tr>
    <tr><td>DXFLayer</td><td>layers</td><td><code>layers.document_id -> files.id</code> (логическая связь по UUID)</td></tr>
    <tr><td>DXFContent</td><td>content</td><td><code>content.document_id -> files.id</code> (логическая связь по UUID)</td></tr>
    <tr><td>DXFEntity</td><td>Таблица конкретного слоя</td><td>Таблица берется из <code>layers.schema_name</code> + <code>layers.table_name</code></td></tr>
</table>

<p><b>Важно:</b> в текущей реализации связи задаются на уровне приложения по UUID (через поля <code>document_id</code> и параметры репозиториев).</p>

<h3>Основные элементы окна</h3>
<ul>
    <li><b>DXF-файлы:</b> список выбранных файлов и текущий файл для настройки параметров импорта.</li>
    <li><b>Подключение к БД:</b> выбор сохраненного подключения и проверка активной сессии.</li>
    <li><b>Режим импорта:</b> перезапись слоев, обновление с добавлением или только добавление новых объектов.</li>
    <li><b>Схемы слоев/файлов:</b> выбор, куда создавать и обновлять таблицы.</li>
    <li><b>Импортировать только слои:</b> ускоренный режим без полной файловой структуры (возможны ограничения по данным файла).</li>
    <li><b>Транслитерация:</b> преобразование имен слоев для совместимости имен таблиц и внешних систем.</li>
</ul>
""",
    "MAIN_DIALOG":"""
<h2>Руководство по основному окну</h2>

<h3>Вкладка «Импорт» (DXF → БД)</h3>
<ul>
    <li><b>Открыть DXF:</b> добавляет один или несколько DXF-файлов в рабочее дерево.</li>
    <li><b>Выбрать область на карте:</b> выделяет объекты по геометрии (прямоугольник/круг/полигон) и правилу отбора (внутри/снаружи/пересечение).</li>
    <li><b>Фильтр выделения:</b> выбор файла, поиск по слоям, включение/выключение слоев и применение фильтра к сущностям.</li>
    <li><b>Сохранить в файл:</b> создает новый DXF только из выделенных объектов. Рекомендуется, когда нужна 100% сохранность полного набора атрибутов конкретной выборки перед импортом.</li>
    <li><b>Импорт в БД:</b> открывает специализированный диалог, где задаются режим записи и схемы БД.</li>
</ul>

<h3>Вкладка «Экспорт» (БД → DXF)</h3>
<ul>
    <li><b>Редактор подключений:</b> создание, редактирование и выбор конфигураций PostgreSQL/PostGIS.</li>
    <li><b>Выбор подключения и схемы:</b> определяет источник DXF-данных в БД.</li>
    <li><b>Обновить файлы:</b> перечитывает список файлов из выбранной схемы.</li>
    <li><b>Экспортировать:</b> достает файл из БД и формирует DXF на диске (или для открытия в QGIS).</li>
</ul>


<h3>Фактическая модель хранения (кратко)</h3>
<table border="1" cellpadding="4" cellspacing="0">
    <tr><th>Объект</th><th>Фактическое хранение</th><th>Как связывается</th></tr>
    <tr><td>Файл DXF</td><td>Таблица <code>files</code></td><td><code>id</code>, <code>filename</code></td></tr>
    <tr><td>Слой DXF</td><td>Таблица <code>layers</code></td><td><code>document_id</code> указывает на документ</td></tr>
    <tr><td>Содержимое файла</td><td>Таблица <code>content</code> (BYTEA)</td><td><code>document_id</code> указывает на документ</td></tr>
    <tr><td>Сущности слоя</td><td>Отдельная таблица для слоя в <code>layer schema</code></td><td>Имя таблицы берется из <code>layers.table_name</code></td></tr>
</table>

<h3>Вкладка «Настройки»</h3>
<ul>
    <li><b>Язык интерфейса:</b> переключение локализации без перезапуска плагина.</li>
    <li><b>Логирование:</b> включает/выключает журнал операций для диагностики.</li>
</ul>

<h3>Горячая клавиша</h3>
<ul>
    <li><b>Ctrl+Tab:</b> переключение между вкладками.</li>
</ul>
"""
}