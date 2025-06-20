from typing import List, Optional
from sqlalchemy.orm import declarative_base

from .converter_dxf_to_postgis import convert_entity_to_postgis

Base = declarative_base()

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, Session, close_all_sessions
from ..logger.logger import Logger
from datetime import datetime, timezone
from . import models
from ..dxf.dxf_handler import DXFHandler
import os

# Шаблон URL для подключения к базе данных
PATTERN_DATABASE_URL = 'postgresql://{username}:{password}@{address}:{port}/{dbname}'

# Глобальные переменные для хранения текущего движка, сессии и кэша файлов
engine = None
SessionLocal = None

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

        # Создаем схемы если их нет
        #_create_schemas()
        
        # НЕ создаем все таблицы сразу - они будут созданы по мере необходимости
        # Base.metadata.create_all(bind=engine)

        # Логируем успешное подключение
        Logger.log_message(f"Подключено к базе данных PostgreSQL '{dbname}' по адресу {address}:{port} с пользователем '{username}'.")

        session = SessionLocal()
        
        return session
    except Exception as e:
        Logger.log_error(f"Ошибка подключения к базе данных PostgreSQL '{dbname}' по адресу {address}:{port} с пользователем '{username}': {str(e)}")
        return None

def _create_schemas():
    """Создание необходимых схем в базе данных"""
    try:
        with engine.connect() as connection:
            # Проверяем и создаем расширение PostGIS
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS file_schema;"))
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS layer_schema;"))
            connection.commit()
        Logger.log_message("Схемы и расширение PostGIS успешно созданы или уже существуют.")
    except Exception as e:
        Logger.log_error(f"Ошибка при создании схем: {str(e)}")

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
                          custom_filename: str = None) -> bool:
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
    Returns:
        True в случае успеха, иначе False
    """
    
    try:
        session = _connect_to_database(username, password, host, port, dbname)
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
            layer_class = create_layer_table_if_not_exists(layer_name, layer_schema, file_schema)
            if not layer_class:
                continue
            
            # Используем file_id только если файл был сохранен
            file_id = file_record.id if file_record else None
            
            # В зависимости от режима маппирования выбираем различную стратегию
            if mapping_mode == "always_overwrite":
                # Удаляем все существующие записи для этого файла и слоя (если файл сохранен)
                if file_id:
                    session.query(layer_class).filter_by(file_id=file_id).delete()
                else:
                    # Если экспортируем только слои, удаляем все записи в таблице слоя
                    session.query(layer_class).delete()
                session.commit()
                Logger.log_message(f"Все существующие записи в слое {layer_name} удалены")
                
                # Добавляем новые записи
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

