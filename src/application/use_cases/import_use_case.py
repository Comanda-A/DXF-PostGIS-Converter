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
    
    def execute(
        self,
        connection: ConnectionConfigDTO,
        configs: list[ImportConfigDTO]
    ) -> tuple[AppResult[Unit], str]:
        "return (result, report)"

        report_lines = []
        report_lines.append("Starting DXF import process")
        docs: dict[str, DXFDocument] = {}
        
        # check connection
        if not connection:
            return AppResult.fail("No connection"), "\n".join(report_lines)

        report_lines.append(f"Connection config validated: {connection.host}:{connection.port}/{connection.database}")

        # check config
        if not configs:
            return AppResult.fail("No configs"), "\n".join(report_lines)
        
        report_lines.append(f"Import configurations loaded: {len(configs)} file(s) to process")

        self._session = inject.instance(DBSession)

        # check files
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

        # check connect
        connect_result = self._session.connect(connection)
        if connect_result.is_fail:
            error_msg = f"Database connection failed: {connect_result.error}"
            report_lines.append(f"ERROR: {error_msg}")
            return AppResult.fail(connect_result.error), "\n".join(report_lines)

        report_lines.append(f"Successfully connected to database")

        # check repos
        for config in configs:
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

        report_lines.append("All database schemas verified successfully")

        # start import
        try:
            previews_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "previews")
            )

            for config in configs:
                report_lines.append(f"\n--- Processing file: {config.filename} ---")

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

                # Импортируем только выбранные сущности
                doc = source_doc
                doc_repo = None
                content_repo = None
                layer_repo = None

                if not config.import_layers_only:
                    report_lines.append(f"Importing document structure to schema '{config.file_schema}'")

                    doc_repo = self._session._get_document_repository(config.file_schema).value
                    content_repo = self._session._get_content_repository(config.file_schema).value
                    layer_repo = self._session._get_layer_repository(config.file_schema).value

                    report_lines.append(f"All repositories initialized for schema '{config.file_schema}'")

                    now = datetime.now()
                    doc_to_save = DXFDocument(
                        id=source_doc.id,
                        filename=source_doc.filename,
                        filepath=source_doc.filepath,
                        layers=selected_layers,
                        content=DXFContent(document_id=source_doc.id, content=filtered_content),
                        upload_date=now,
                        update_date=now,
                    )

                    if doc_repo.exists(config.filename).value:
                        report_lines.append(f"Document already exists in database, updating...")
                        existing_doc_result = doc_repo.get_by_filename(config.filename)
                        if existing_doc_result.is_success and existing_doc_result.value:
                            existing_doc = existing_doc_result.value
                            doc_to_save = DXFDocument(
                                id=source_doc.id,
                                filename=source_doc.filename,
                                filepath=source_doc.filepath,
                                layers=selected_layers,
                                content=DXFContent(document_id=source_doc.id, content=filtered_content),
                                upload_date=existing_doc.upload_date,
                                update_date=now,
                            )

                        result = doc_repo.update(doc_to_save)
                        report_lines.append(f"Document updated successfully (ID: {result.value.id})")
                    else:
                        report_lines.append(f"Creating new document in database...")
                        result = doc_repo.create(doc_to_save)
                        report_lines.append(f"Document created successfully (ID: {result.value.id})")

                    doc = result.value

                    content_result = content_repo.get_by_document_id(doc.id)
                    if content_result.is_fail:
                        report_lines.append(f"Creating new content record for document...")
                        dxf_content = content_repo.create(
                            DXFContent(document_id=doc.id, content=filtered_content)
                        ).value
                        report_lines.append(f"Content record created (size: {len(filtered_content)} bytes)")
                    else:
                        report_lines.append(f"Updating existing content record...")
                        dxf_content = content_result.value
                        dxf_content = content_repo.update(
                            DXFContent(id=dxf_content.id, document_id=doc.id, content=filtered_content)
                        ).value
                        report_lines.append(f"Content record updated (size: {len(filtered_content)} bytes)")
                else:
                    report_lines.append(f"Importing layers only to schema '{config.layer_schema}'")

                # Обработка слоев - выполняется для обоих режимов
                if doc and layer_repo:
                    layers_processed = 0
                    doc_short_id = self._make_short_id(doc.id)

                    if not config.import_layers_only:
                        for layer in selected_layers:
                            base_table_name = self._transliterate_layer_name(layer.name) if config.transliterate_layer_names else layer.name

                            table_name = f"l{doc_short_id}_{base_table_name}" if doc_short_id else base_table_name

                            ex_layer_result = layer_repo.get_by_document_id_and_layer_name(doc.id, layer.name)

                            if ex_layer_result.is_fail:
                                report_lines.append(f"Creating new layer record: '{layer.name}' (table: {table_name})")
                                ex_layer = layer_repo.create(
                                    DXFLayer(
                                        document_id=doc.id,
                                        name=layer.name,
                                        schema_name=config.layer_schema,
                                        table_name=table_name,
                                    )
                                ).value
                                layers_processed += 1
                            else:
                                ex_layer = ex_layer_result.value
                                if ex_layer.schema_name != config.layer_schema or ex_layer.table_name != table_name:
                                    report_lines.append(f"Layer '{layer.name}' already exists but with different schema/table, creating new layer record")
                                    ex_layer = layer_repo.create(
                                        DXFLayer(
                                            document_id=doc.id,
                                            name=layer.name,
                                            schema_name=config.layer_schema,
                                            table_name=table_name,
                                        )
                                    ).value
                                    layers_processed += 1
                                else:
                                    report_lines.append(f"Layer '{layer.name}' already exists in target schema, skipping")

                        report_lines.append(f"Layers processed: {layers_processed} created, {len(selected_layers) - layers_processed} existing")

                    report_lines.append(f"\nSaving layer entities for schema '{config.layer_schema}'...")

                    total_entities = 0

                    for layer in selected_layers:
                        base_table_name = self._transliterate_layer_name(layer.name) if config.transliterate_layer_names else layer.name
                        table_name = f"l{doc_short_id}_{base_table_name}" if doc_short_id else base_table_name

                        entity_repo_result = self._session._get_entity_repository(config.layer_schema, table_name)
                        if entity_repo_result.is_fail:
                            report_lines.append(f"ERROR: Failed to get repository for layer '{layer.name}': {entity_repo_result.error}")
                            continue

                        entity_repo = entity_repo_result.value
                        report_lines.append(f"Processing layer '{layer.name}' (table: {table_name})...")

                        layer_entity_count = 0
                        for entity in layer.entities.values():
                            if not entity.is_selected:
                                continue

                            check_result = entity_repo.get_by_name_and_type(entity.name, entity.entity_type)

                            if check_result.is_success and check_result.value:
                                result = entity_repo.update(entity)
                                if result.is_success:
                                    total_entities += 1
                                    layer_entity_count += 1
                            else:
                                result = entity_repo.create(entity)
                                if result.is_success:
                                    total_entities += 1
                                    layer_entity_count += 1
                                else:
                                    report_lines.append(f"WARNING: Failed to create entity '{entity.name}': {result.error}")

                        report_lines.append(f"Layer '{layer.name}' completed: {layer_entity_count} entities saved")

                    report_lines.append(f"Total entities saved: {total_entities}")

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