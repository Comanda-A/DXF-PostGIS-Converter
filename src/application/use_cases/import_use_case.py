import inject
import os
import tempfile
from datetime import datetime
from unidecode import unidecode

from ...domain.entities import DXFDocument, DXFContent, DXFLayer, DXFEntity
from ...domain.repositories import IActiveDocumentRepository
from ...domain.services import IDXFReader, IDXFWriter

from ...application.dtos import ImportConfigDTO, ConnectionConfigDTO, ImportMode
from ...application.results import AppResult, Unit
from ...application.interfaces import ILogger
from ...application.database import DBSession

class ImportUseCase:
    """Вариант использования: Импортировать DXF файл"""

    def __init__(
        self,
        active_repo: IActiveDocumentRepository,
        dxf_reader: IDXFReader,
        dxf_writer: IDXFWriter,
        logger: ILogger
    ):
        self._active_repo = active_repo
        self._dxf_reader = dxf_reader
        self._dxf_writer = dxf_writer
        self._logger = logger
    
    def _transliterate_layer_name(self, layer_name: str) -> str:
        """Транслитерирует русские названия слоев в английские"""
        return unidecode(layer_name)
    
    def _make_short_id(self, uuid_obj) -> str:
        """Создает компактный идентификатор из UUID (первые 6 символов без дефисов)"""
        if not uuid_obj:
            return ""
        uuid_str = str(uuid_obj).replace("-", "")
        return uuid_str[:6]
    
    def _table_exists(self, schema_name: str, table_name: str) -> AppResult[bool]:
        """Проверяет существование таблицы в указанной схеме"""
        tables_result = self._session.get_tables(schema_name)
        if tables_result.is_fail:
            return AppResult.fail(f"Failed to get tables for schema '{schema_name}': {tables_result.error}")
        
        tables = tables_result.value
        exists = table_name in tables
        return AppResult.success(exists)
    
    def _get_layer_table_name(
        self, 
        config: ImportConfigDTO, 
        layer_name: str, 
        doc_short_id: str
    ) -> str:
        """Определяет название таблицы для слоя на основе настроек"""
        
        # Проверяем, есть ли индивидуальные настройки для этого слоя
        layer_settings = config.layer_settings.get(layer_name)
        
        if layer_settings:
            # Если есть настройки слоя
            if layer_settings.create_new_table:
                # Создаем новую таблицу
                base_name = layer_settings.new_table_name or layer_name
                
                # Транслитерация, если требуется
                if config.transliterate_layer_names:
                    base_name = self._transliterate_layer_name(base_name)
                
                # Добавляем префикс, если требуется
                if config.prefix_check and doc_short_id:
                    return f"l{doc_short_id}_{base_name}"
                else:
                    return base_name
            else:
                # Используем существующую таблицу
                return layer_settings.existing_table_name
        else:
            # Нет индивидуальных настроек - используем глобальные настройки
            base_name = layer_name
            
            # Транслитерация, если требуется
            if config.transliterate_layer_names:
                base_name = self._transliterate_layer_name(base_name)
            
            # Добавляем префикс, если требуется
            if config.prefix_check and doc_short_id:
                return f"l{doc_short_id}_{base_name}"
            else:
                return base_name
    
    def execute(
        self,
        connection: ConnectionConfigDTO,
        configs: list[ImportConfigDTO]
    ) -> tuple[AppResult[Unit], str]:
        "return (result, report)"

        report_lines = []
        report_lines.append("Starting DXF import process")
        docs: dict[str, DXFDocument] = {}
        
        # Проверяем конфиг подключения
        if not connection:
            return AppResult.fail("No connection"), "\n".join(report_lines)

        report_lines.append(f"Connection config validated: {connection.host}:{connection.port}/{connection.database}")

        # Проверяем конфиг импорта
        if not configs:
            return AppResult.fail("No configs"), "\n".join(report_lines)
        
        report_lines.append(f"Import configurations loaded: {len(configs)} file(s) to process")

        # Проверяем файлы
        for config in configs:
            result = self._active_repo.get_by_filename(config.filename)
            if result.is_success and result.value:
                docs[config.filename] = result.value
                report_lines.append(f"Document loaded from active repository: '{config.filename}'")
            else:
                error_msg = f"Document '{config.filename}' not found. {result.error}"
                report_lines.append(f"ERROR: {error_msg}")
                return AppResult.fail(error_msg), "\n".join(report_lines)
        
        report_lines.append("All source documents successfully loaded from active repository")

        # Создаем сессию
        self._session = inject.instance(DBSession)

        # Подключаемся к БД
        connect_result = self._session.connect(connection)
        if connect_result.is_fail:
            error_msg = f"Database connection failed: {connect_result.error}"
            report_lines.append(f"ERROR: {error_msg}")
            return AppResult.fail(connect_result.error), "\n".join(report_lines)

        report_lines.append(f"Successfully connected to database")

        # Проверяем существование схем и таблиц из конфига импорта
        for config in configs:
            # Проверка схемы файлов
            result = self._session.schema_exists(config.file_schema)
            if result.is_fail:
                error_msg = f"File schema check error: {result.error}"
                report_lines.append(f"ERROR: {error_msg}")
                return AppResult.fail(error_msg), "\n".join(report_lines)
            elif not result.value:
                error_msg = f"File schema '{config.file_schema}' does not exist in database"
                report_lines.append(f"ERROR: {error_msg}")
                return AppResult.fail(error_msg), "\n".join(report_lines)
            
            report_lines.append(f"File schema verified: '{config.file_schema}'")
            
            # Проверка схемы слоев
            result = self._session.schema_exists(config.layer_schema)
            if result.is_fail:
                error_msg = f"Layer schema check error: {result.error}"
                report_lines.append(f"ERROR: {error_msg}")
                return AppResult.fail(error_msg), "\n".join(report_lines)  
            elif not result.value:
                error_msg = f"Layer schema '{config.layer_schema}' does not exist in database"
                report_lines.append(f"ERROR: {error_msg}")
                return AppResult.fail(error_msg), "\n".join(report_lines)
            
            report_lines.append(f"Layer schema verified: '{config.layer_schema}'")
            
            # Проверка настроек слоев
            if config.layer_settings:
                report_lines.append(f"\nValidating layer settings for '{config.filename}'...")

                for layer_name, layer_settings in config.layer_settings.items():
                    
                    # Выбрано: создать новую таблицу
                    if layer_settings.create_new_table:
                        # Название таблицы не выбрано
                        if not layer_settings.new_table_name:
                            error_msg = f"Layer '{layer_name}': new table name is required when 'create_new_table' is enabled"
                            report_lines.append(f"ERROR: {error_msg}")
                            return AppResult.fail(error_msg), "\n".join(report_lines)
                        
                        # Пробуем найти таблицу
                        table_exists_result = self._table_exists(
                            config.layer_schema, 
                            layer_settings.new_table_name
                        )

                        # Ошибка при выполнении
                        if table_exists_result.is_fail:
                            error_msg = f"Layer '{layer_name}': failed to check if table '{layer_settings.new_table_name}' exists: {table_exists_result.error}"
                            report_lines.append(f"ERROR: {error_msg}")
                            return AppResult.fail(error_msg), "\n".join(report_lines)
                        
                        # Если таблица есть
                        if table_exists_result.value:
                            report_lines.append(f"Layer '{layer_name}': table '{layer_settings.new_table_name}' already exists, will use existing table")
                        else: # таблицы нет - создадим
                            report_lines.append(f"  Layer '{layer_name}': will create new table '{layer_settings.new_table_name}'")
                            
                    else: # Если используется существующая таблица
                        
                        if not layer_settings.existing_table_name:
                            error_msg = f"Layer '{layer_name}': existing_table_name is required when create_new_table=False"
                            report_lines.append(f"ERROR: {error_msg}")
                            return AppResult.fail(error_msg), "\n".join(report_lines)
                        
                        table_exists_result = self._table_exists(
                            config.layer_schema, 
                            layer_settings.existing_table_name
                        )
                        
                        if table_exists_result.is_fail:
                            error_msg = f"Layer '{layer_name}': failed to check if table '{layer_settings.existing_table_name}' exists: {table_exists_result.error}"
                            report_lines.append(f"ERROR: {error_msg}")
                            return AppResult.fail(error_msg), "\n".join(report_lines)
                        
                        if not table_exists_result.value:
                            error_msg = f"Layer '{layer_name}': table '{layer_settings.existing_table_name}' does not exist in schema '{config.layer_schema}'"
                            report_lines.append(f"ERROR: {error_msg}")
                            return AppResult.fail(error_msg), "\n".join(report_lines)
                        
                        # Таблица выбрана и найдена
                        report_lines.append(f"Layer '{layer_name}': will use existing table '{layer_settings.existing_table_name}'")

        report_lines.append("All database schemas and layer settings verified successfully")

        # start import
        try:
            previews_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "previews")
            )

            for config in configs:
                report_lines.append(f"\n--- Processing file: {config.filename} ---")
                report_lines.append(f"Settings: prefix_check={config.prefix_check}, transliterate={config.transliterate_layer_names}")

                source_doc = docs[config.filename]
                selected_handles = self._get_selected_handles(source_doc)
                use_selected_subset = bool(selected_handles)

                if use_selected_subset:
                    selected_layers = [
                        layer
                        for layer in source_doc.layers.values()
                        if any(entity.is_selected for entity in layer.entities.values())
                    ]
                else:
                    selected_layers = list(source_doc.layers.values())

                preview_source_path, temp_source_file = self._prepare_preview_source(source_doc)
                temp_preview_file = ""
                filtered_content = b""

                try:
                    if not preview_source_path:
                        error_msg = f"Source file for '{config.filename}' is unavailable"
                        report_lines.append(f"ERROR: {error_msg}")
                        return AppResult.fail(error_msg), "\n".join(report_lines)

                    if use_selected_subset:
                        fd, temp_preview_file = tempfile.mkstemp(suffix=".dxf")
                        os.close(fd)

                        preview_save_result = self._dxf_writer.save_selected_by_handles(
                            source_filepath=preview_source_path,
                            output_path=temp_preview_file,
                            selected_handles=selected_handles,
                        )
                        if preview_save_result.is_fail:
                            error_msg = f"Failed to prepare selected DXF for '{config.filename}': {preview_save_result.error}"
                            report_lines.append(f"ERROR: {error_msg}")
                            return AppResult.fail(error_msg), "\n".join(report_lines)

                        preview_result = self._dxf_reader.save_svg_preview(
                            filepath=temp_preview_file,
                            output_dir=previews_dir,
                            filename=config.filename,
                        )
                        if preview_result.is_success:
                            report_lines.append(f"Preview saved: {preview_result.value}")
                        else:
                            report_lines.append(f"WARNING: Failed to save preview for '{config.filename}': {preview_result.error}")

                        with open(temp_preview_file, "rb") as preview_file:
                            filtered_content = preview_file.read()
                    else:
                        preview_result = self._dxf_reader.save_svg_preview(
                            filepath=preview_source_path,
                            output_dir=previews_dir,
                            filename=config.filename,
                        )
                        if preview_result.is_success:
                            report_lines.append(f"Preview saved: {preview_result.value}")
                        else:
                            report_lines.append(f"WARNING: Failed to save preview for '{config.filename}': {preview_result.error}")

                        if source_doc.content:
                            filtered_content = source_doc.content.content
                        elif preview_source_path and os.path.exists(preview_source_path):
                            with open(preview_source_path, "rb") as preview_file:
                                filtered_content = preview_file.read()
                        else:
                            filtered_content = b""

                finally:
                    if temp_source_file and os.path.exists(temp_source_file):
                        os.remove(temp_source_file)
                    if temp_preview_file and os.path.exists(temp_preview_file):
                        os.remove(temp_preview_file)

                # Начинаем импорт
                doc = source_doc
                doc_repo = None
                content_repo = None
                layer_repo = None
                
                # short_id открытого файла
                doc_short_id = self._make_short_id(doc.id)

                # Импорт мета
                if not config.import_layers_only:
                    report_lines.append(f"Importing document structure to schema '{config.file_schema}'")

                    # Создаем репы
                    doc_repo = self._session._get_document_repository(config.file_schema).value
                    content_repo = self._session._get_content_repository(config.file_schema).value
                    layer_repo = self._session._get_layer_repository(config.file_schema).value

                    report_lines.append(f"All repositories initialized for schema '{config.file_schema}'")

                    # Поиск файлов с таким же названием
                    if doc_repo.exists(config.filename).value:
                        report_lines.append(f"Document already exists in database, updating...")
                        # Получаем файл на изменение
                        existing_doc_result = doc_repo.get_by_filename(config.filename)
                        existing_doc = existing_doc_result.value
                        existing_doc.update_date = datetime.now()
                        result = doc_repo.update(existing_doc)
                        report_lines.append(f"Document updated successfully (ID: {result.value.id})")
                    
                    # Создаем новый файл
                    else:
                        report_lines.append(f"Creating new document in database...")
                        doc_to_save = DXFDocument(
                            id=doc.id,
                            filename=doc.filename,
                            upload_date=datetime.now(),
                            update_date=datetime.now()
                        )
                        result = doc_repo.create(doc_to_save)
                        report_lines.append(f"Document created successfully (ID: {result.value.id})")

                    # Док в БД
                    db_doc = result.value

                    # обновляем short_id файла в бд
                    doc_short_id = self._make_short_id(db_doc.id)

                    # Поиск контента в БД
                    db_content = content_repo.get_by_document_id(db_doc.id).value

                    # Контент есть
                    if db_content:
                        report_lines.append(f"Updating existing content record...")
                        db_content.content = filtered_content
                        db_content = content_repo.update(db_content).value
                        report_lines.append(f"Content record created (size: {len(filtered_content)} bytes)")
                    
                    # Контента нет
                    else:
                        report_lines.append(f"Creating new content record for document...")
                        db_content = content_repo.create(
                            DXFContent(document_id=db_doc.id, content=filtered_content)
                        ).value
                        report_lines.append(f"Content record updated (size: {len(filtered_content)} bytes)")

                    layers_processed = 0

                    # Поиск слоев в БД
                    for layer in doc.layers.values():
                        # Пропускаем невыбранные слои
                        if not layer.is_selected:
                            continue
                        
                        # Название таблицы для слоя на основе конфига
                        table_name = self._get_layer_table_name(config, layer.name, doc_short_id)

                        # Поиск записи слоя в БД
                        ex_layer = layer_repo.get_by_document_id_and_layer_name(db_doc.id, layer.name).value

                        # Если запись слоя есть
                        if ex_layer:
                            report_lines.append(f"Layer '{layer.name}' already exists in database")
                            # Если схема или таблица не совпадают
                            if ex_layer.schema_name != config.layer_schema or ex_layer.table_name != table_name:
                                # Проверяем существование указанной ранее таблицы
                                if self._table_exists(ex_layer.schema_name, ex_layer.table_name).value:
                                    # Таблица существует - можно переименовать/переместить
                                    self._session.rename_table(ex_layer.schema_name, ex_layer.table_name, config.layer_schema, table_name).value   
                                # Обновляем запись слоя с новыми данными
                                ex_layer.schema_name = config.layer_schema
                                ex_layer.table_name = table_name
                                layer_repo.update(ex_layer).value
                        # Записи слоя нет - создаем новую
                        else:
                            ex_layer = layer_repo.create(
                                DXFLayer(
                                    document_id=db_doc.id,
                                    name=layer.name,
                                    schema_name=config.layer_schema,
                                    table_name=table_name
                                )
                            ).value
                            report_lines.append(f"Layer '{layer.name}' created in database with table '{table_name}'")
                        
                        layers_processed += 1
                    
                    report_lines.append(f"Document structure import completed for '{config.filename}'. {layers_processed} layers processed.")

                # Импорт слоев
                if config.import_mode == ImportMode.OVERWRITE_LAYERS:

                    # Поиск слоев в БД
                    for layer in doc.layers.values():
                        # Пропускаем невыбранные слои
                        if not layer.is_selected:
                            continue
                        
                        # Название таблицы для слоя на основе конфига
                        table_name = self._get_layer_table_name(config, layer.name, doc_short_id)

                        # Получаем репозиторий сущностей для слоя
                        entity_repo_result = self._session._get_entity_repository(config.layer_schema, table_name)
                        if entity_repo_result.is_fail:
                            report_lines.append(f"ERROR: Failed to get repository for layer '{layer.name}': {entity_repo_result.error}")
                            continue

                        entity_repo = entity_repo_result.value
                        entity_repo.delete_all()  # Удаляем все существующие объекты слоя
                        entities_processed = 0

                        for entity in layer.entities.values():
                            if not entity.is_selected:
                                continue
                            
                            result = entity_repo.create(entity)
                            if result.is_fail:
                                report_lines.append(
                                    f"WARNING: Failed to create entity '{entity.name}' in '{table_name}': {result.error}"
                                )
                            entities_processed += 1
                        
                        report_lines.append(f"Layer '{layer.name}': {entities_processed} entities imported with OVERWRITE_LAYERS mode")
                elif config.import_mode == ImportMode.OVERWRITE_OBJECTS:
                    
                    # Поиск слоев в БД
                    for layer in doc.layers.values():
                        # Пропускаем невыбранные слои
                        if not layer.is_selected:
                            continue
                        
                        # Название таблицы для слоя на основе конфига
                        table_name = self._get_layer_table_name(config, layer.name, doc_short_id)

                        # Получаем репозиторий сущностей для слоя
                        entity_repo_result = self._session._get_entity_repository(config.layer_schema, table_name)
                        if entity_repo_result.is_fail:
                            report_lines.append(f"ERROR: Failed to get repository for layer '{layer.name}': {entity_repo_result.error}")
                            continue

                        entity_repo = entity_repo_result.value
                        entities_processed = 0

                        for entity in layer.entities.values():
                            if not entity.is_selected:
                                continue
                            
                            existing_entity = entity_repo.get_by_name_and_type(entity.name, entity.entity_type).value  # Проверяем существование объекта
                            if existing_entity:
                                entity_repo.update(
                                    DXFEntity(
                                        id=existing_entity.id,
                                        name=entity.name,
                                        entity_type=entity.entity_type,
                                        attributes=entity.attributes,
                                        geometries=entity.geometries,
                                        extra_data=entity.extra_data
                                    )
                                ).value
                            else:
                                result = entity_repo.create(entity)

                            entities_processed += 1
                        
                        report_lines.append(f"Layer '{layer.name}': {entities_processed} entities imported with OVERWRITE_OBJECTS mode")
                else:  # ImportMode.ADD_OBJECTS
                    
                    # Поиск слоев в БД
                    for layer in doc.layers.values():
                        # Пропускаем невыбранные слои
                        if not layer.is_selected:
                            continue
                        
                        # Название таблицы для слоя на основе конфига
                        table_name = self._get_layer_table_name(config, layer.name, doc_short_id)

                        # Получаем репозиторий сущностей для слоя
                        entity_repo_result = self._session._get_entity_repository(config.layer_schema, table_name)
                        if entity_repo_result.is_fail:
                            report_lines.append(f"ERROR: Failed to get repository for layer '{layer.name}': {entity_repo_result.error}")
                            continue

                        entity_repo = entity_repo_result.value
                        entities_processed = 0

                        for entity in layer.entities.values():
                            if not entity.is_selected:
                                continue
                            
                            existing_entity = entity_repo.get_by_name_and_type(entity.name, entity.entity_type).value  # Проверяем существование объекта
                            if not existing_entity:
                                # Объекта нет - создаем новый
                                result = entity_repo.create(entity)

                            entities_processed += 1
                        
                        report_lines.append(f"Layer '{layer.name}': {entities_processed} entities imported with ADD_OBJECTS mode")

            self._session.commit()
            self._session.close()
            report_lines.append("\n" + "="*50)
            report_lines.append("IMPORT COMPLETED SUCCESSFULLY")
            report_lines.append(f"Total files processed: {len(configs)}")
            report_lines.append("="*50)
            
            return AppResult.success(Unit()), "\n".join(report_lines)
                
        except Exception as e:
            error_msg = f"Import error: {str(e)}"
            report_lines.append(error_msg)
            self._logger.error(error_msg)

            report_lines.append("Rolling back transaction...")
            
            result = self._session.rollback()
            self._session.close()
            
            report_lines.append("Transaction rolled back")
            report_lines.append("IMPORT FAILED")
            
            return AppResult.fail(str(e)), "\n".join(report_lines)
    
    def generate_pre_import_report(
        self,
        connection: ConnectionConfigDTO,
        configs: list[ImportConfigDTO]
    ) -> str:
        """
        Генерирует подробный предварительный отчет о том, что произойдет при импорте
        """
        report_lines = []
        report_lines.append("PRE-IMPORT REPORT\n")
        
        # Информация о подключении
        report_lines.append("DATABASE CONNECTION:\n")
        if connection:
            report_lines.append(f"DBMS: {connection.db_type}\n")
            report_lines.append(f"Host: {connection.host}:{connection.port}\n")
            report_lines.append(f"Database: {connection.database}\n")
            report_lines.append(f"Username: {connection.username}\n")
        else:
            report_lines.append("ERROR: No connection provided\n")
            return "".join(report_lines)
        
        if not configs:
            report_lines.append("ERROR: No import configurations provided\n")
            return "".join(report_lines)
        
        # Информация о файлах
        report_lines.append(f"\nFILES TO IMPORT:\n")
        report_lines.append(f"Total files: {len(configs)}\n")
        
        docs: dict[str, DXFDocument] = {}
        for i, config in enumerate(configs, 1):
            report_lines.append(f"\nFile {i}: {config.filename}\n")
            
            # Попытка загрузить документ
            result = self._active_repo.get_by_filename(config.filename)
            if result.is_success and result.value:
                doc = result.value
                docs[config.filename] = doc
                report_lines.append(f"  Status: Found in active repository\n")
                report_lines.append(f"  Layers: {len(doc.layers)}\n")
                total_entities = sum(len(layer.entities) for layer in doc.layers.values())
                report_lines.append(f"  Total entities: {total_entities}\n")
            else:
                report_lines.append(f"  Status: NOT FOUND (error: {result.error})\n")
        
        # Проверка подключения к БД
        report_lines.append(f"\nDATABASE CONNECTIVITY:\n")
        self._session = inject.instance(DBSession)
        connect_result = self._session.connect(connection)
        
        if connect_result.is_fail:
            report_lines.append(f"Status: CONNECTION FAILED\n")
            report_lines.append(f"Error: {connect_result.error}\n")
            return "".join(report_lines)
        
        report_lines.append(f"Status: Connected successfully\n")
        
        # Информация о схемах и таблицах
        report_lines.append(f"\nSCHEMAS & TABLES:\n")
        
        for config in configs:
            if config.filename not in docs:
                continue
            
            doc = docs[config.filename]
            report_lines.append(f"\nFile: {config.filename}\n")
            report_lines.append(f"  Import mode: {config.import_mode.value[0]}\n")
            
            # Проверка схем
            layer_schema_exists = self._session.schema_exists(config.layer_schema).value
            file_schema_exists = self._session.schema_exists(config.file_schema).value
            
            report_lines.append(f"  Layer schema: '{config.layer_schema}' {'✓ EXISTS' if layer_schema_exists else '✗ NOT FOUND'}\n")
            report_lines.append(f"  File schema: '{config.file_schema}' {'✓ EXISTS' if file_schema_exists else '✗ NOT FOUND'}\n")
            
            # Информация по слоям
            doc_short_id = self._make_short_id(doc.id)
            report_lines.append(f"\n  Layers:\n")
            
            for layer in doc.layers.values():
                
                if not layer.is_selected:
                    continue

                table_name = self._get_layer_table_name(config, layer.name, doc_short_id)
                layer_settings = config.layer_settings.get(layer.name)
                entity_count = len(layer.entities)
                
                report_lines.append(f"    • {layer.name}\n")
                report_lines.append(f"      Table: {table_name}\n")
                report_lines.append(f"      Entities: {entity_count}\n")
                
                # Информация о таблице
                if layer_schema_exists:
                    table_exists_result = self._table_exists(config.layer_schema, table_name)
                    if table_exists_result.is_success:
                        exists = table_exists_result.value
                        if exists:
                            report_lines.append(f"      Table status: ✓ EXISTS in DB\n")
                            if config.import_mode == ImportMode.OVERWRITE_LAYERS:
                                report_lines.append(f"      Action: DELETE ALL objects and re-import\n")
                            elif config.import_mode == ImportMode.OVERWRITE_OBJECTS:
                                report_lines.append(f"      Action: UPDATE existing objects, ADD new ones\n")
                            else:
                                report_lines.append(f"      Action: ADD only new objects (skip existing)\n")
                        else:
                            report_lines.append(f"      Table status: ✗ WILL BE CREATED\n")
                    else:
                        report_lines.append(f"      Table status: ? UNKNOWN (check error)\n")
                
                # Особые настройки слоя
                if layer_settings:
                    if not layer_settings.create_new_table:
                        report_lines.append(f"      Mode: Using EXISTING table '{layer_settings.existing_table_name}'\n")
                    else:
                        report_lines.append(f"      Mode: Creating NEW table\n")
            
            # Опции импорта
            report_lines.append(f"\n  Import options:\n")
            report_lines.append(f"    • Import layers only: {config.import_layers_only}\n")
            report_lines.append(f"    • Transliterate layer names: {config.transliterate_layer_names}\n")
            report_lines.append(f"    • Add prefix to layer names: {config.prefix_check}\n")
        
        self._session.close()
        
        report_lines.append(f"\nEND OF REPORT\n")
        
        return "".join(report_lines)

    def _get_selected_handles(self, document: DXFDocument) -> set[str]:
        selected_handles: set[str] = set()
        for layer in document.layers.values():
            for entity in layer.entities.values():
                if not entity.is_selected:
                    continue
                handle = str(entity.attributes.get("handle", "")).strip().upper()
                if handle:
                    selected_handles.add(handle)
        return selected_handles

    def _prepare_preview_source(self, document: DXFDocument) -> tuple[str, str]:
        if document.filepath and os.path.exists(document.filepath):
            return document.filepath, ""

        if not document.content:
            return "", ""

        fd, temp_source_file = tempfile.mkstemp(suffix=".dxf")
        os.close(fd)
        with open(temp_source_file, "wb") as tmp_file:
            tmp_file.write(document.content.content)
        return temp_source_file, temp_source_file