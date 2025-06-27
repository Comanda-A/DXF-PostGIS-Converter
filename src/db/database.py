from typing import List, Optional
from sqlalchemy.orm import declarative_base

from .converter_dxf_to_postgis import convert_entity_to_postgis

Base = declarative_base()

from sqlalchemy import create_engine, text, inspect, MetaData, Table
from sqlalchemy.orm import sessionmaker, Session, close_all_sessions
from ..logger.logger import Logger
from datetime import datetime, timezone
from . import models
from ..dxf.dxf_handler import DXFHandler
from ..gui.column_mapping_dialog import ColumnMappingDialog
import os

# Шаблон URL для подключения к базе данных
PATTERN_DATABASE_URL = 'postgresql://{username}:{password}@{address}:{port}/{dbname}'

# Глобальные переменные для хранения текущего движка, сессии и кэша файлов
engine = None
SessionLocal = None

def ensure_postgis_extension(session: Session) -> bool:
    """
    Проверяет наличие расширения PostGIS в базе данных и создает его при необходимости
    
    Args:
        session: Сессия базы данных
        
    Returns:
        True если расширение доступно, иначе False
    """
    try:
        with session.bind.connect() as connection:
            # Проверяем наличие расширения PostGIS
            result = connection.execute(text("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_extension WHERE extname = 'postgis'
                );
            """))
            
            extension_exists = result.scalar()
            
            if not extension_exists:
                Logger.log_message("Расширение PostGIS не найдено, пытаемся создать...")
                
                # Пытаемся создать расширение PostGIS
                try:
                    connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                    connection.commit()
                    Logger.log_message("Расширение PostGIS успешно создано")
                    return True
                except Exception as create_error:
                    Logger.log_error(f"Не удалось создать расширение PostGIS: {str(create_error)}")
                    
                    # Проверяем, доступно ли расширение для установки
                    try:
                        available_result = connection.execute(text("""
                            SELECT EXISTS(
                                SELECT 1 FROM pg_available_extensions WHERE name = 'postgis'
                            );
                        """))
                        
                        if available_result.scalar():
                            Logger.log_error("Расширение PostGIS доступно, но не удалось его установить. Проверьте права доступа.")
                        else:
                            Logger.log_error("Расширение PostGIS недоступно на сервере PostgreSQL. Обратитесь к администратору.")
                    except Exception:
                        Logger.log_error("Не удалось проверить доступность расширения PostGIS")
                    
                    return False
            else:
                Logger.log_message("Расширение PostGIS уже установлено")
                return True
                
    except Exception as e:
        Logger.log_error(f"Ошибка при проверке расширения PostGIS: {str(e)}")
        return False

def _show_schema_selector_dialog(schemas):
    """
    Показывает диалог выбора схемы
    Args:
        schemas: Список схем для отображения в диалоге выбора
    Returns:
        Выбранная схема или None если диалог отменен
    """
    try:
        
        # Импортируем здесь, чтобы избежать циклических импортов
        from ..gui.schema_selector_dialog import SchemaSelectorDialog
        from qgis.PyQt.QtWidgets import QApplication
          # Получаем главное окно приложения
        app = QApplication.instance()
        if app is None:
            return None
            
        # Находим активное главное окно QGIS или любое видимое окно верхнего уровня
        main_window = None
        active_window = app.activeWindow()
        
        # Сначала пытаемся найти активное окно
        if active_window and active_window.isVisible():
            main_window = active_window
        else:
            # Ищем главное окно QGIS
            for widget in app.topLevelWidgets():
                if widget.objectName() == 'QgisApp' and widget.isVisible():
                    main_window = widget
                    break
            
            # Если не нашли главное окно QGIS, берем любое видимое окно верхнего уровня
            if not main_window:
                for widget in app.topLevelWidgets():
                    if widget.isVisible() and widget.isWindow():
                        main_window = widget
                        break
        
        # Создаем диалог выбора схемы с готовым списком схем
        dialog = SchemaSelectorDialog(schemas, main_window)
        
        # Убеждаемся, что диалог отображается поверх всех окон
        if main_window:
            dialog.raise_()
            dialog.activateWindow()
        
        if dialog.exec_() == SchemaSelectorDialog.Accepted:
            return dialog.get_selected_schema()
        else:
            return None
            
    except Exception as e:
        Logger.log_error(f"Ошибка при показе диалога выбора схемы: {str(e)}")
        return None


def _find_in_schemas(username, password, host, port, dbname, search_function, file_schema=None):
    """
    Универсальная функция для поиска в схемах с автоматическим диалогом выбора
    
    Args:
        session: Сессия базы данных
        username: Имя пользователя для подключения к БД
        password: Пароль для подключения к БД
        host: Адрес сервера БД
        port: Порт сервера БД
        dbname: Имя базы данных
        search_function: Функция поиска, принимающая (file_class) и возвращающая результат
        file_schema: Схема для поиска (опционально)
        
    Returns:
        Словарь с ключами 'result' (результат поиска), 'schema' (использованная схема)
    """
    try:
        from qgis.core import QgsSettings
        
        # Получаем список существующих схем
        existing_schemas = get_schemas(username, password, host, port, dbname)
        Logger.log_message(f"Найдено схем: {existing_schemas}")
        if not existing_schemas:
            Logger.log_warning("Не удалось получить список схем из базы данных")
            return {'result': None, 'schema': None}
        
        # Если схема не указана, используем сохранённую схему
        if file_schema is None:
            settings = QgsSettings()
            file_schema = settings.value("DXFPostGIS/lastConnection/fileSchema", 'file_schema')
        
        # Проверяем, существует ли указанная схема
        if file_schema in existing_schemas:
            try:
                # Создаём класс для указанной схемы
                file_class = models.create_file_table(file_schema)
                # Пытаемся найти в указанной схеме
                result = search_function(file_class)
                if result is not None and (not hasattr(result, '__len__') or len(result) > 0):
                    return {'result': result, 'schema': file_schema}
            except Exception as schema_error:
                Logger.log_warning(f"Не удалось выполнить поиск в схеме '{file_schema}': {str(schema_error)}")
        else:
            Logger.log_warning(f"Схема '{file_schema}' не существует в базе данных")
        
        # Если не удалось найти в указанной схеме, пробуем схемы по умолчанию
        default_schemas = ['file_schema', 'public']
        for default_schema in default_schemas:
            if default_schema == file_schema:
                continue  # Уже пробовали
            if default_schema not in existing_schemas:
                Logger.log_warning(f"Схема по умолчанию '{default_schema}' не существует в базе данных")
                continue  # Пропускаем несуществующие схемы
            try:
                file_class = models.create_file_table(default_schema)
                result = search_function(file_class)
                if result is not None and (not hasattr(result, '__len__') or len(result) > 0):
                    Logger.log_message(f"Результат найден в схеме '{default_schema}'")
                    return {'result': result, 'schema': default_schema}
            except Exception:
                continue
        
        # Если ничего не найдено в схемах по умолчанию, показываем диалог выбора схемы
        selected_schema = _show_schema_selector_dialog(existing_schemas)
        
        if selected_schema:
            try:
                file_class = models.create_file_table(selected_schema)
                result = search_function(file_class)
                if result is not None and (not hasattr(result, '__len__') or len(result) > 0):
                    Logger.log_message(f"Результат найден в выбранной схеме '{selected_schema}'")
                    
                    # Сохраняем выбранную схему в настройки
                    settings = QgsSettings()
                    settings.setValue("DXFPostGIS/lastConnection/fileSchema", selected_schema)
                    
                    return {'result': result, 'schema': selected_schema}
                else:
                    Logger.log_warning(f"В выбранной схеме '{selected_schema}' ничего не найдено")
            except Exception as e:
                Logger.log_error(f"Ошибка при поиске в выбранной схеме '{selected_schema}': {str(e)}")
        
        return {'result': None, 'schema': None}
        
    except Exception as e:
        Logger.log_error(f"Ошибка в универсальной функции поиска по схемам: {str(e)}")
        return {'result': None, 'schema': None}


# ----------------------
# Основные функции работы с базой данных
# ----------------------

def _connect_to_database(username, password, address, port, dbname) -> Session:
    """Создание подключения к базе данных"""
    try:
        global engine, SessionLocal
        # Закрываем текущие сессии, если они есть
        if 'SessionLocal' in globals() and SessionLocal is not None:
            close_all_sessions()

        # Формируем URL базы данных
        db_url = PATTERN_DATABASE_URL.format(
            username=username, 
            password=password,
            address=address, 
            port=port, 
            dbname=dbname
        )

        # Создаем новый движок и сессию с правильными настройками кодировки
        engine = create_engine(
            db_url,
            connect_args={
                'client_encoding': 'WIN1251',  # более компактное хранение кириллицы
            }
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # Логируем успешное подключение
        Logger.log_message(f"Подключено к базе данных PostgreSQL '{dbname}' по адресу {address}:{port} с пользователем '{username}'.")

        session = SessionLocal()
        
        return session
    except Exception as e:
        Logger.log_error(f"Ошибка подключения к базе данных PostgreSQL '{dbname}' по адресу {address}:{port} с пользователем '{username}': {str(e)}")
        return None


def get_schemas(username, password, host, port, dbname) -> List[str]:
    """
    Получение списка всех схем в базе данных
    
    Args:
        username: Имя пользователя для подключения к БД
        password: Пароль для подключения к БД
        host: Адрес сервера БД
        port: Порт сервера БД
        dbname: Имя базы данных
        
    Returns:
        Список названий схем
    """
    try:
        session = _connect_to_database(username, password, host, port, dbname)
        if session is None:
            Logger.log_message("Не удалось подключиться к базе данных")
            return []
            
        with session.bind.connect() as connection:
            result = connection.execute(text("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast', 'pg_temp_1', 'pg_toast_temp_1')
                ORDER BY schema_name;
            """))
            schemas = [row[0] for row in result]
            Logger.log_message(f"Найдено схем: {len(schemas)}")
            return schemas
    except Exception as e:
        Logger.log_error(f"Ошибка при получении списка схем: {str(e)}")
        return []

def create_schema(username, password, host, port, dbname, schema_name: str) -> bool:
    """
    Создание новой схемы в базе данных
    
    Args:
        username: Имя пользователя для подключения к БД
        password: Пароль для подключения к БД
        host: Адрес сервера БД
        port: Порт сервера БД
        dbname: Имя базы данных
        schema_name: Название схемы для создания
        
    Returns:
        True если схема создана успешно, иначе False
    """
    try:
        session = _connect_to_database(username, password, host, port, dbname)
        if session is None:
            Logger.log_error("Не удалось подключиться к базе данных")
            return False
            
        with session.bind.connect() as connection:
            # Проверяем существование схемы
            result = connection.execute(text("""
                SELECT 1 FROM information_schema.schemata 
                WHERE schema_name = :schema_name
            """), {"schema_name": schema_name})
            
            if result.fetchone():
                Logger.log_message(f"Схема '{schema_name}' уже существует")
                return True
                
            # Создаем новую схему
            connection.execute(text(f'CREATE SCHEMA "{schema_name}";'))
            connection.commit()
            Logger.log_message(f"Схема '{schema_name}' успешно создана")
            return True
    except Exception as e:
        Logger.log_error(f"Ошибка при создании схемы '{schema_name}': {str(e)}")
        return False

# ----------------------
# Методы создания сущностей
# ----------------------

def create_file_record(session: Session, filename: str, file_content: bytes, file_schema: str = 'file_schema'):
    """
    Создает запись о DXF файле в базе данных
    
    Args:
        session: Сессия базы данных
        filename: Имя файла
        file_content: Содержимое файла в бинарном формате
        file_schema: Схема для размещения таблицы файлов

    Returns:
        Экземпляр модели DxfFile или None в случае ошибки
    """
    try:
        now = datetime.now(timezone.utc)
        
        # Создаем или получаем класс таблицы файлов для указанной схемы
        file_class = models.create_file_table(file_schema)
        
        # Создаем таблицу, если она не существует
        file_class.__table__.create(engine, checkfirst=True)
        
        # Проверяем, существует ли файл с таким именем
        existing_file = session.query(file_class).filter(file_class.filename == filename).first()
        
        if (existing_file):
            # Обновляем существующий файл
            existing_file.file_content = file_content
            existing_file.update_date = now
            session.commit()
            Logger.log_message(f"Файл {filename} обновлен в базе данных.")
            return existing_file
        else:
            # Создаем новую запись
            new_file = file_class(
                filename=filename,
                file_content=file_content,
                upload_date=now,
                update_date=now
            )
            session.add(new_file)
            session.commit()
            Logger.log_message(f"Файл {filename} добавлен в базу данных в схему {file_schema}.")
            return new_file
    except Exception as e:
        session.rollback()
        Logger.log_error(f"Ошибка при создании записи файла {filename}: {str(e)}")
        return None

def create_layer_table_if_not_exists(layer_name: str, layer_schema: str = 'layer_schema', file_schema: str = 'file_schema') -> Optional[type]:
    """
    Создает таблицу для слоя, если она не существует
    
    Args:
        layer_name: Имя слоя
        layer_schema: Схема для размещения таблицы слоя
        file_schema: Схема где находится таблица файлов
        
    Returns:
        Класс таблицы для слоя или None в случае ошибки
    """
    try:
        # Нормализуем имя таблицы (заменяем пробелы и дефисы на подчеркивания)
        table_name = layer_name.replace(' ', '_').replace('-', '_')
        
        # Проверяем существование таблицы
        inspector = inspect(engine)
        table_exists = inspector.has_table(table_name, schema=layer_schema)
        
        if not table_exists:
            # Создаем класс таблицы
            layer_class = models.create_layer_table(layer_name, layer_schema, file_schema)
            # Создаем таблицу в базе данных
            layer_class.__table__.create(engine, checkfirst=True)
            Logger.log_message(f"Создана таблица для слоя {layer_name} в схеме {layer_schema}")
            return layer_class
        else:
            # Возвращаем существующий класс таблицы
            return models.create_layer_table(layer_name, layer_schema, file_schema)
    except Exception as e:
        Logger.log_error(f"Ошибка при создании таблицы для слоя {layer_name} в схеме {layer_schema}: {str(e)}")
        return None


# ----------------------
# Методы экспорта
# ----------------------

def export_dxf_to_database(username, password, host, port, dbname, dxf_handler: DXFHandler, file_path: str, 
                          mapping_mode: str = "always_overwrite", layer_schema: str = 'layer_schema', 
                          file_schema: str = 'file_schema', export_layers_only: bool = False, 
                          custom_filename: str = None, column_mapping_configs: dict = None) -> bool:
    """
    Экспортирует DXF файл в базу данных
    
    Args:
        username: Имя пользователя для подключения к БД
        password: Пароль для подключения к БД
        host: Адрес сервера БД
        port: Порт сервера БД
        dbname: Имя базы данных
        dxf_handler: Экземпляр обработчика DXF
        file_path: Путь к DXF файлу
        mapping_mode: Режим маппирования слоев (always_overwrite, geometry, notes, both)
        layer_schema: Схема для размещения таблиц слоев
        file_schema: Схема для размещения таблицы файлов
        export_layers_only: Экспортировать только слои (без сохранения файла)        
        custom_filename: Пользовательское название файла для сохранения в БД (опционально)
        column_mapping_configs: Словарь настроек сопоставления столбцов для каждого слоя (опционально)
    Returns:
        True в случае успеха, иначе False
    """
    
    try:
        session = _connect_to_database(username, password, host, port, dbname)
        if session is None:
            Logger.log_error("Не удалось подключиться к базе данных")
            return False
            
        # Проверяем и устанавливаем расширение PostGIS при необходимости
        if not ensure_postgis_extension(session):
            Logger.log_error("Расширение PostGIS недоступно. Работа с геометрией невозможна.")
            return False
            
        # Получаем имя файла из пути (оригинальное название)
        original_filename = os.path.basename(file_path)
        # Используем пользовательское название файла или оригинальное
        filename_for_db = custom_filename if custom_filename else original_filename
        
        Logger.log_message(f"Начало экспорта DXF файла в базу данных...")
        Logger.log_message(f"Оригинальное название файла: {original_filename}")
        Logger.log_message(f"Название для БД: {filename_for_db}")
        Logger.log_message(f"Путь к файлу: {file_path}")
        Logger.log_message(f"Режим маппирования: {mapping_mode}")
        Logger.log_message(f"Схема для слоев: {layer_schema}")
        Logger.log_message(f"Схема для файлов: {file_schema}")
        Logger.log_message(f"Экспорт только слоев: {export_layers_only}")
        
        file_record = None
        
        # Создаем запись о файле только если не экспортируем только слои
        if not export_layers_only:
            # Читаем содержимое файла
            with open(file_path, 'rb') as f:
                file_content = f.read()
            # Создаем запись о файле в указанной схеме с названием для БД
            file_record = create_file_record(session, filename_for_db, file_content, file_schema)
            if not file_record:
                return False
          # Получаем слои DXF файла используя оригинальное название
        layers_entities = dxf_handler.get_entities_for_export(original_filename)
        
        # Для каждого слоя создаем таблицу и записываем сущности
        for layer_name, entities in layers_entities.items():
            Logger.log_message(f"Обработка слоя: {layer_name}")
              # Проверяем, нужно ли сопоставление столбцов для этого слоя
            mapping_check = needs_column_mapping(session, layer_name, layer_schema)
            Logger.log_message(f"Проверка сопоставления для слоя {layer_name}: {mapping_check['reason']}")
            
            # Определяем конфигурацию сопоставления для этого слоя
            layer_mapping_config = None
            
            # Сначала проверяем специфичную конфигурацию для слоя
            if column_mapping_configs and layer_name in column_mapping_configs:
                layer_mapping_config = column_mapping_configs[layer_name]
                Logger.log_message(f"Найдена специфичная конфигурация сопоставления для слоя {layer_name}")
            # Затем проверяем глобальную конфигурацию
            elif column_mapping_configs and 'global_pattern' in column_mapping_configs:
                layer_mapping_config = column_mapping_configs['global_pattern']
                Logger.log_message(f"Используется глобальная конфигурация сопоставления для слоя {layer_name}")
            # Проверяем глобальную конфигурацию с другим ключом
            elif column_mapping_configs and 'global' in column_mapping_configs:
                layer_mapping_config = column_mapping_configs['global']
                Logger.log_message(f"Используется глобальная конфигурация (global) для слоя {layer_name}")
                
            # Создаем таблицу слоя если она не существует (только для стандартного случая)
            if not mapping_check['needs_mapping'] or not layer_mapping_config:
                layer_class = create_layer_table_if_not_exists(layer_name, layer_schema, file_schema)
                if not layer_class:
                    Logger.log_error(f"Не удалось создать таблицу для слоя {layer_name}")
                    continue
            
            # Используем file_id только если файл был сохранен
            file_id = file_record.id if file_record else None
            
            # В зависимости от режима маппирования выбираем различную стратегию
            if mapping_mode == "always_overwrite":
                
                # Если нужно сопоставление столбцов И есть конфигурация сопоставления
                if mapping_check['needs_mapping'] and layer_mapping_config:
                    Logger.log_message(f"Применяем сопоставление столбцов для слоя {layer_name}")
                    Logger.log_message(f"Конфигурация сопоставления: {layer_mapping_config}")
                    
                    # Используем функцию применения сопоставления столбцов
                    success = apply_column_mapping(session, layer_name, layer_mapping_config, 
                                                 entities, layer_schema, file_id)
                    if not success:
                        Logger.log_warning(f"Не удалось применить сопоставление столбцов для слоя {layer_name}, используем стандартный способ")
                        # Удаляем существующие записи
                        if file_id:
                            session.query(layer_class).filter_by(file_id=file_id).delete()
                        else:
                            session.query(layer_class).delete()
                        session.commit()
                        _add_new_entities(session, entities, layer_class, file_id)
                else:
                    # Стандартный способ: удаляем существующие записи и добавляем новые
                    Logger.log_message(f"Используем стандартный способ экспорта для слоя {layer_name}")
                    if file_id:
                        session.query(layer_class).filter_by(file_id=file_id).delete()
                    else:
                        # Если экспортируем только слои, удаляем все записи в таблице слоя
                        session.query(layer_class).delete()
                    session.commit()
                    Logger.log_message(f"Все существующие записи в слое {layer_name} удалены")
                    
                    # Добавляем новые сущности стандартным способом
                    _add_new_entities(session, entities, layer_class, file_id)
            
            Logger.log_message(f"Экспортирован слой {layer_name} из файла {filename_for_db}")
              # Генерируем превью файла только если файл был сохранен
        if file_record:
            _create_output_dxf(file_path, filename_for_db, dxf_handler)
        return True
    except Exception as e:
        session.rollback()
        # Получаем имя файла для логирования ошибок
        error_filename = custom_filename if custom_filename else os.path.basename(file_path)
        Logger.log_error(f"Ошибка при экспорте DXF файла {error_filename} в базу данных: {str(e)}")
        return False


def _create_output_dxf(file_path : str, filename: str, dxf_handler: DXFHandler) -> None:
    """Создание SVG превью DXF файла"""
    doc = dxf_handler.simle_read_dxf_file(file_path)
    dxf_handler.save_svg_preview(doc, doc.modelspace(), filename)

def _add_new_entities(session: Session, entities, layer_class, file_id: Optional[int]) -> None:
    """
    Добавляет новые сущности в таблицу слоя
    
    Args:
        session: Сессия базы данных
        entities: Список сущностей для добавления
        layer_class: Класс модели таблицы слоя
        file_id: ID файла (может быть None если экспортируем только слои)
    """
    try:
        for entity in entities:
            # Преобразуем DXF сущность в формат PostGIS
            postgis_entity = convert_entity_to_postgis(entity)
            
            if postgis_entity:
                # Создаем новый экземпляр модели слоя
                # Добавляем file_id только если он существует
                layer_entity_data = {
                    'geom_type': postgis_entity['geom_type'],
                    'geometry': postgis_entity['geometry'],
                    'notes': postgis_entity.get('notes', None),
                    'extra_data': postgis_entity.get('extra_data', None)
                }
                
                if file_id is not None:
                    layer_entity_data['file_id'] = file_id
                
                layer_entity = layer_class(**layer_entity_data)
                session.add(layer_entity)
        
        # Сохраняем изменения в базе данных
        session.commit()
        Logger.log_message(f"Добавлено {len(entities)} новых сущностей в слой")
    except Exception as e:
        session.rollback()
        Logger.log_error(f"Ошибка при добавлении новых сущностей: {str(e)}")


# ----------------------
# Метод удаления
# ----------------------

def delete_dxf_file(username, password, host, port, dbname, file_id: int, file_schema=None) -> bool:
    """
    Удаляет DXF файл из базы данных по его ID
    
    Args:
        username: Имя пользователя для подключения к БД
        password: Пароль для подключения к БД
        host: Адрес сервера БД
        port: Порт сервера БД
        dbname: Имя базы данных
        file_id: ID файла в базе данных
        file_schema: Схема для поиска файла (опционально)
        
    Returns:
        True в случае успеха, иначе False
    """
    try:
        session = _connect_to_database(username, password, host, port, dbname)
        if session is None:
            return False
        
        def search_file_for_deletion(file_class):
            """Функция поиска файла для удаления в указанной схеме"""
            return session.query(file_class).filter_by(id=file_id).first()
        
        # Используем универсальную функцию поиска
        result = _find_in_schemas(username, password, host, port, dbname, search_file_for_deletion, file_schema)
        
        file_record = result['result']
        actual_schema = result['schema']
        
        if not file_record:
            Logger.log_warning(f"Файл с ID {file_id} не найден в базе данных")
            return False
            
        # Получаем имя файла для логирования
        filename = file_record.filename
        
        # Удаляем файл
        session.delete(file_record)
        session.commit()
        
        Logger.log_message(f"Файл {filename} (ID: {file_id}) успешно удален из схемы '{actual_schema}'")
        return True
        
    except Exception as e:
        if 'session' in locals():
            session.rollback()
        Logger.log_error(f"Ошибка при удалении DXF файла с ID {file_id}: {str(e)}")
        return False


# ----------------------
# Методы запросов
# ----------------------

def get_table_columns(username, password, host, port, dbname, table_name, schema_name='public'):
    """
    Получает информацию о столбцах существующей таблицы
    
    Args:
        username: Имя пользователя для подключения к БД
        password: Пароль для подключения к БД
        host: Адрес сервера БД
        port: Порт сервера БД
        dbname: Имя базы данных
        table_name: Имя таблицы
        schema_name: Схема таблицы
        
    Returns:
        Список словарей с информацией о столбцах [{'name': str, 'type': str, 'nullable': bool}, ...]
    """
    try:
        session = _connect_to_database(username, password, host, port, dbname)
        if session is None:
            return []
            
        with session.bind.connect() as connection:
            result = connection.execute(text("""
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length
                FROM information_schema.columns 
                WHERE table_schema = :schema_name 
                AND table_name = :table_name
                ORDER BY ordinal_position
            """), {'schema_name': schema_name, 'table_name': table_name})
            
            columns = []
            for row in result:
                columns.append({
                    'name': row[0],
                    'type': row[1],
                    'nullable': row[2] == 'YES',
                    'default': row[3],
                    'max_length': row[4]
                })
            
            Logger.log_message(f"Получены столбцы таблицы {schema_name}.{table_name}: {len(columns)} столбцов")
            return columns
            
    except Exception as e:
        Logger.log_error(f"Ошибка при получении столбцов таблицы {schema_name}.{table_name}: {str(e)}")
        return []

def table_exists(username, password, host, port, dbname, table_name, schema_name='public'):
    """
    Проверяет существование таблицы в базе данных
    
    Args:
        username: Имя пользователя для подключения к БД
        password: Пароль для подключения к БД
        host: Адрес сервера БД
        port: Порт сервера БД
        dbname: Имя базы данных
        table_name: Имя таблицы
        schema_name: Схема таблицы
        
    Returns:
        True если таблица существует, иначе False
    """
    try:
        session = _connect_to_database(username, password, host, port, dbname)
        if session is None:
            return False
            
        with session.bind.connect() as connection:
            result = connection.execute(text("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.tables 
                    WHERE table_schema = :schema_name 
                    AND table_name = :table_name
                )
            """), {'schema_name': schema_name, 'table_name': table_name})
            
            exists = result.scalar()
            Logger.log_message(f"Таблица {schema_name}.{table_name} {'существует' if exists else 'не существует'}")
            return exists
            
    except Exception as e:
        Logger.log_error(f"Ошибка при проверке существования таблицы {schema_name}.{table_name}: {str(e)}")
        return False

def get_all_dxf_files(username, password, host, port, dbname, file_schema=None):
    """
    Получает список всех DXF файлов в базе данных
    
    Args:
        username: Имя пользователя для подключения к БД
        password: Пароль для подключения к БД
        host: Адрес сервера БД
        port: Порт сервера БД
        dbname: Имя базы данных
        file_schema: Схема для поиска файлов (опционально)
        
    Returns:
        Словарь с ключами 'files' (список файлов) и 'schema' (использованная схема)
    """
    try:
        session = _connect_to_database(username, password, host, port, dbname)
        if session is None:
            return {'files': [], 'schema': None}
        
        def search_files(file_class):
            """Функция поиска файлов в указанной схеме"""
            db_files = session.query(file_class).all()
            files = []
            for file in db_files:
                files.append({
                    'id': file.id,
                    'filename': file.filename,
                    'upload_date': file.upload_date,
                    'update_date': file.update_date
                })
            return files
        
        # Используем универсальную функцию поиска
        result = _find_in_schemas(username, password, host, port, dbname, search_files, file_schema)
        
        return {'files': result['result'] or [], 'schema': result['schema']}
            
    except Exception as e:
        Logger.log_error(f"Ошибка при получении списка DXF файлов: {str(e)}")
        return {'files': [], 'schema': None}

def get_dxf_file_by_id(username, password, host, port, dbname, file_id: int, file_schema=None) -> Optional[models.DxfFile]:
    """
    Получает DXF файл по его ID
    
    Args:
        username: Имя пользователя для подключения к БД
        password: Пароль для подключения к БД
        host: Адрес сервера БД
        port: Порт сервера БД
        dbname: Имя базы данных
        file_id: ID файла
        file_schema: Схема для поиска файла (опционально)
        
    Returns:
        Объект DxfFile или None, если файл не найден
    """
    try:
        session = _connect_to_database(username, password, host, port, dbname)
        if session is None:
            return None
        
        def search_file(file_class):
            """Функция поиска файла по ID в указанной схеме"""
            return session.query(file_class).filter_by(id=file_id).first()
        
        # Используем универсальную функцию поиска
        result = _find_in_schemas(username, password, host, port, dbname, search_file, file_schema)
        
        return result['result']
            
    except Exception as e:
        Logger.log_error(f"Ошибка при получении DXF файла с ID {file_id}: {str(e)}")
        return None

def apply_column_mapping(session, layer_name, mapping_config, entities, layer_schema='layer_schema', file_id=None):
    """
    Применяет настройки сопоставления столбцов при экспорте сущностей
    
    Args:
        session: Сессия базы данных
        layer_name: Имя слоя
        mapping_config: Конфигурация сопоставления столбцов
        entities: Список сущностей для экспорта
        layer_schema: Схема слоя
        file_id: ID файла (может быть None если экспортируем только слои)
        
    Returns:
        True в случае успеха, иначе False
    """
    try:
        if not mapping_config:
            Logger.log_message("Настройки сопоставления столбцов не предоставлены")
            return False
            
        Logger.log_message(f"Применение сопоставления столбцов для слоя {layer_name}")
        Logger.log_message(f"Конфигурация: {mapping_config}")
        
        strategy = mapping_config.get('strategy', 'mapping_only')
        mappings = mapping_config.get('mappings', {})
        new_columns = mapping_config.get('new_columns', [])
        target_table = mapping_config.get('target_table')
        
        if not target_table:
            Logger.log_error("Целевая таблица не указана в настройках сопоставления")
            return False        # Получаем класс существующей таблицы
        table_name = target_table.replace(' ', '_').replace('-', '_')
        
        # Создаем динамический класс для существующей таблицы
        from . import models
        
        # Отражаем существующую таблицу из базы данных
        metadata = MetaData()
        existing_table = Table(table_name, metadata, autoload_with=session.bind, schema=layer_schema)
        
        # Создаем динамический класс для работы с существующей таблицей
        layer_class = type(
            f"ExistingLayer_{table_name}",
            (Base,),
            {
                '__table__': existing_table,
                '__mapper_args__': {'primary_key': [existing_table.c.id] if 'id' in existing_table.c else []}
            }
        )
        
        # Если стратегия включает добавление столбцов
        if strategy in ['mapping_add_columns', 'mapping_add_backup']:
            _add_columns_to_table(session, layer_class, new_columns)
            
            # После добавления столбцов обновляем метаданные таблицы
            metadata = MetaData()
            existing_table = Table(table_name, metadata, autoload_with=session.bind, schema=layer_schema)
            
            # Пересоздаем динамический класс с обновленной структурой таблицы
            layer_class = type(
                f"ExistingLayer_{table_name}",
                (Base,),
                {
                    '__table__': existing_table,
                    '__mapper_args__': {'primary_key': [existing_table.c.id] if 'id' in existing_table.c else []}
                }
            )
            
        # Если стратегия включает создание backup
        if strategy in ['mapping_backup', 'mapping_add_backup']:
            _create_backup_table(session, layer_class, layer_name, layer_schema)
              # Очищаем существующие записи для этого файла, если file_id указан
        if file_id is not None:
            # Используем сопоставленное имя столбца для file_id
            file_id_column = mappings.get('file_id', 'file_id')
            if hasattr(existing_table.c, file_id_column):
                delete_query = session.query(layer_class).filter(getattr(existing_table.c, file_id_column) == file_id)
                deleted_count = delete_query.count()
                delete_query.delete()
                Logger.log_message(f"Удалено {deleted_count} существующих записей для {file_id_column}={file_id}")
            else:
                Logger.log_warning(f"Столбец {file_id_column} не найден в таблице, пропускаем очистку записей")
        else:
            # Если file_id не указан, очищаем всю таблицу
            deleted_count = session.query(layer_class).count()
            session.query(layer_class).delete()
            Logger.log_message(f"Удалено {deleted_count} записей из таблицы {table_name}")
            
        session.commit()
        
        # Применяем сопоставление к каждой сущности
        added_count = 0
        for entity in entities:
            try:
                # Конвертируем сущность в PostGIS формат
                postgis_data = convert_entity_to_postgis(entity)
                
                if not postgis_data:
                    Logger.log_warning(f"Не удалось преобразовать сущность {entity}")
                    continue                # Применяем сопоставление полей
                mapped_data = _apply_field_mapping(postgis_data, mappings)
                
                # Добавляем file_id если предоставлен, используя сопоставленное имя столбца
                if file_id is not None:
                    file_id_column = mappings.get('file_id', 'file_id')
                    mapped_data[file_id_column] = file_id
                
                # Фильтруем данные, оставляя только те поля, которые существуют в целевой таблице
                filtered_data = {}
                for field_name, field_value in mapped_data.items():
                    if hasattr(existing_table.c, field_name):
                        filtered_data[field_name] = field_value
                    else:
                        Logger.log_warning(f"Поле {field_name} не существует в целевой таблице, пропускаем")
                
                # Создаем новую запись в таблице
                layer_record = layer_class(**filtered_data)
                session.add(layer_record)
                added_count += 1
                
            except Exception as e:
                Logger.log_error(f"Ошибка при обработке сущности: {str(e)}")
                continue
                
        session.commit()
        Logger.log_message(f"Успешно применено сопоставление столбцов: добавлено {added_count} из {len(entities)} сущностей")
        return True
        
    except Exception as e:
        session.rollback()
        Logger.log_error(f"Ошибка при применении сопоставления столбцов для слоя {layer_name}: {str(e)}")
        return False

def _add_columns_to_table(session, table_class, columns):
    """Добавляет новые столбцы в существующую таблицу"""
    try:
        # Получаем имя таблицы и схему из объекта Table
        table_obj = table_class.__table__
        table_name = table_obj.name
        schema_name = table_obj.schema
        
        # Маппинг типов столбцов на основе DxfLayerBase из models.py
        column_types_mapping = {
            'id': 'INTEGER PRIMARY KEY',
            'file_id': 'INTEGER',
            'geometry': 'GEOMETRY(GEOMETRYZ, 4326)',
            'geom_type': 'VARCHAR',
            'notes': 'TEXT',
            'extra_data': 'JSONB'
        }
        
        for column_name in columns:
            # Определяем тип столбца на основе маппинга
            column_type = column_types_mapping.get(column_name, "TEXT")
            
            alter_sql = text(f"""
                ALTER TABLE "{schema_name}"."{table_name}" 
                ADD COLUMN IF NOT EXISTS "{column_name}" {column_type}
            """)
            
            session.execute(alter_sql)
            Logger.log_message(f"Добавлен столбец {column_name} ({column_type}) в таблицу {schema_name}.{table_name}")
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        Logger.log_error(f"Ошибка при добавлении столбцов: {str(e)}")

def _create_backup_table(session, table_class, layer_name, layer_schema):
    """Создает backup таблицу с оригинальной структурой"""
    try:
        from datetime import datetime
        
        # Получаем имя таблицы из объекта Table
        table_obj = table_class.__table__
        original_table = table_obj.name
        backup_table = f"{original_table}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_sql = text(f"""
            CREATE TABLE "{layer_schema}"."{backup_table}" AS 
            SELECT * FROM "{layer_schema}"."{original_table}"
        """)
        
        session.execute(backup_sql)
        session.commit()
        
        Logger.log_message(f"Создана backup таблица: {layer_schema}.{backup_table}")
        
    except Exception as e:
        session.rollback()
        Logger.log_error(f"Ошибка при создании backup таблицы: {str(e)}")

def _apply_field_mapping(entity_data, mappings):
    """Применяет сопоставление полей к данным сущности"""
    mapped_data = {}
    
    for dxf_field, value in entity_data.items():
        # Если есть сопоставление, используем его
        if dxf_field in mappings:
            db_field = mappings[dxf_field]
            if db_field:  # Проверяем, что сопоставленное поле не пустое
                mapped_data[db_field] = value
        else:
            # Иначе используем оригинальное название поля (только если такое поле не игнорируется)
            mapped_data[dxf_field] = value
    
    return mapped_data

def get_tables_in_schema(username, password, host, port, dbname, schema_name='public'):
    """
    Получает список всех таблиц в указанной схеме
    
    Args:
        username: Имя пользователя для подключения к БД
        password: Пароль для подключения к БД
        host: Адрес сервера БД
        port: Порт сервера БД
        dbname: Имя базы данных
        schema_name: Схема для поиска таблиц
        
    Returns:
        Список названий таблиц
    """
    try:
        session = _connect_to_database(username, password, host, port, dbname)
        if session is None:
            return []
            
        with session.bind.connect() as connection:
            result = connection.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = :schema_name 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """), {'schema_name': schema_name})
            
            tables = [row[0] for row in result]
            session.close()
            return tables
            
    except Exception as e:
        Logger.log_error(f"Ошибка при получении списка таблиц в схеме {schema_name}: {str(e)}")
        return []

def needs_column_mapping(session, layer_name, layer_schema='layer_schema'):
    """
    Проверяет, нужно ли сопоставление столбцов для данного слоя
    
    Args:
        session: Сессия базы данных
        layer_name: Имя слоя
        layer_schema: Схема слоя
        
    Returns:
        dict: {'needs_mapping': bool, 'existing_columns': list, 'reason': str}
    """
    try:
        # Нормализуем имя таблицы
        table_name = layer_name.replace(' ', '_').replace('-', '_')
        
        # Проверяем существование таблицы используя существующую сессию
        inspector = inspect(session.bind)
        table_exists_flag = inspector.has_table(table_name, schema=layer_schema)
        
        if not table_exists_flag:
            return {
                'needs_mapping': False, 
                'existing_columns': [], 
                'reason': 'Таблица не существует, будет создана новая'
            }
        
        # Получаем столбцы существующей таблицы используя существующую сессию
        with session.bind.connect() as connection:
            result = connection.execute(text("""
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length
                FROM information_schema.columns 
                WHERE table_schema = :schema_name 
                AND table_name = :table_name
                ORDER BY ordinal_position
            """), {'schema_name': layer_schema, 'table_name': table_name})
            
            existing_columns = []
            for row in result:
                existing_columns.append({
                    'name': row[0],
                    'type': row[1],
                    'nullable': row[2] == 'YES',
                    'default': row[3],
                    'max_length': row[4]
                })
        
        # Стандартные столбцы DXF таблицы
        standard_dxf_columns = ['id', 'file_id', 'geometry', 'geom_type', 'notes', 'extra_data']
        
        # Проверяем, есть ли различия в структуре
        existing_column_names = [col['name'] for col in existing_columns]
        
        # Если в существующей таблице отсутствуют стандартные столбцы DXF
        missing_standard_columns = [col for col in standard_dxf_columns if col not in existing_column_names]
        
        # Если в существующей таблице есть дополнительные столбцы, не являющиеся стандартными DXF
        extra_columns = [col for col in existing_column_names if col not in standard_dxf_columns]
        
        if missing_standard_columns or extra_columns:
            reason = []
            if missing_standard_columns:
                reason.append(f"Отсутствуют стандартные DXF столбцы: {', '.join(missing_standard_columns)}")
            if extra_columns:
                reason.append(f"Дополнительные столбцы в существующей таблице: {', '.join(extra_columns)}")
                
            return {
                'needs_mapping': True,
                'existing_columns': existing_columns,
                'reason': '; '.join(reason)
            }
        
        return {
            'needs_mapping': False,
            'existing_columns': existing_columns,
            'reason': 'Структура таблицы соответствует стандартной DXF структуре'
        }
        
    except Exception as e:
        Logger.log_error(f"Ошибка при проверке необходимости сопоставления столбцов: {str(e)}")
        return {
            'needs_mapping': False,
            'existing_columns': [],
            'reason': f'Ошибка проверки: {str(e)}'
        }


# ----------------------
# Основные функции работы с базой данных
# ----------------------
