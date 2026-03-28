import inject

from ...domain.entities import DXFDocument, DXFContent, DXFLayer, DXFEntity
from ...domain.repositories import IActiveDocumentRepository

from ...application.dtos import ImportConfigDTO, ConnectionConfigDTO, ImportMode
from ...application.results import AppResult, Unit
from ...application.interfaces import ILogger
from ...application.database import DBSession

class ImportUseCase:
    """Вариант использования: Импортировать DXF файл"""

    def __init__(
        self,
        active_repo: IActiveDocumentRepository,
        logger: ILogger
    ):
        self._active_repo = active_repo
        self._logger = logger
    
    def execute(
        self,
        connection: ConnectionConfigDTO,
        configs: list[ImportConfigDTO]
    ) -> tuple[AppResult[Unit], str]:
        "return (result, report)"

        report_lines = []
        report_lines.append("Starting DXF import process")
        docs: dict[str, DXFDocument] = {}
        self._session = inject.instance(DBSession)
        
        # check connection
        if not connection:
            return AppResult.fail("No connection"), "\n".join(report_lines)

        report_lines.append(f"Connection config validated: {connection.host}:{connection.port}/{connection.database}")

        # check config
        if not configs:
            return AppResult.fail("No configs"), "\n".join(report_lines)
        
        report_lines.append(f"Import configurations loaded: {len(configs)} file(s) to process")

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
            for config in configs:
                report_lines.append(f"\n--- Processing file: {config.filename} ---")
                
                # Импортируем файлы
                if not config.import_layers_only:
                    report_lines.append(f"Importing document structure to schema '{config.file_schema}'")
                    
                    doc_repo = self._session._get_document_repository(config.file_schema).value
                    content_repo = self._session._get_content_repository(config.file_schema).value
                    layer_repo = self._session._get_layer_repository(config.file_schema).value
                    
                    report_lines.append(f"All repositories initialized for schema '{config.file_schema}'")

                    if doc_repo.exists(config.filename).value:
                        report_lines.append(f"Document already exists in database, updating...")
                        result = doc_repo.update(docs[config.filename])
                        report_lines.append(f"Document updated successfully (ID: {result.value.id})")
                    else:
                        report_lines.append(f"Creating new document in database...")
                        result = doc_repo.create(docs[config.filename])
                        report_lines.append(f"Document created successfully (ID: {result.value.id})")

                    doc = result.value

                    dxf_content = content_repo.get_by_document_id(doc.id).value
                    if dxf_content is None:
                        report_lines.append(f"Creating new content record for document...")
                        dxf_content = content_repo.create(
                            DXFContent(
                                document_id=doc.id,
                                content=docs[config.filename].content.content
                            )
                        ).value
                        report_lines.append(f"Content record created (size: {len(docs[config.filename].content.content)} bytes)")
                    else:
                        report_lines.append(f"Updating existing content record...")
                        dxf_content.content = docs[config.filename].content.content
                        dxf_content = content_repo.update(dxf_content).value
                        report_lines.append(f"Content record updated (size: {len(docs[config.filename].content.content)} bytes)")
                    
                    layers_processed = 0
                    for layer in docs[config.filename].layers.values():
                        ex_layer = layer_repo.get_by_document_id_and_layer_name(doc.id, layer.name).value

                        if ex_layer is None:
                            report_lines.append(f"Creating new layer record: '{layer.name}'")
                            ex_layer = layer_repo.create(
                                DXFLayer(
                                    document_id=doc.id,
                                    name=layer.name,
                                    schema_name=config.layer_schema,
                                    table_name=layer.name
                                )
                            ).value
                            layers_processed += 1
                        else:
                            # если объекты слоя хранятся в другой схеме или таблице, то создаем еще одну сущность слоя
                            if ex_layer.schema_name != config.layer_schema or ex_layer.table_name != layer.table_name:
                                report_lines.append(f"Layer '{layer.name}' already exists but with different schema/table, creating new layer record")
                                ex_layer = layer_repo.create(
                                    DXFLayer(
                                        document_id=doc.id,
                                        name=layer.name,
                                        schema_name=config.layer_schema,
                                        table_name=layer.name,
                                    )
                                ).value
                                layers_processed += 1
                            else:
                                report_lines.append(f"Layer '{layer.name}' already exists in target schema, skipping")
                    
                    report_lines.append(f"Layers processed: {layers_processed} created, {len(docs[config.filename].layers.values()) - layers_processed} existing")
                
                # Импортируем слои
                if False:
                    report_lines.append(f"Importing layer entities to schema '{config.layer_schema}' with mode: {config.import_mode.value}")
                    
                    for layer in docs[config.filename].layers.values():
                        report_lines.append(f"  Processing layer: '{layer.name}' ({len(layer.entities.values())} entities)")
                        
                        doc_repo = self._session._get_entity_repository(config.layer_schema, layer.table_name).value
                        
                        entities_created = 0
                        entities_updated = 0
                        entities_skipped = 0
                        
                        for entity in layer.entities.values():
                            ex_entity = doc_repo.get_by_name_and_type(entity.name, entity.entity_type).value
                            if ex_entity is None:
                                # создаем объект вне зависимости от режима
                                ex_entity = doc_repo.create(entity).value
                                entities_created += 1
                            elif config.import_mode == ImportMode.OVERWRITE_OBJECTS:
                                # обновляем существующий объект если выбран режим перезаписи
                                ex_entity = doc_repo.update(
                                    DXFEntity(
                                        id=ex_entity.id,
                                        entity_type=entity.entity_type,
                                        name=entity.name,
                                        attributes=entity.attributes,
                                        geometries=entity.geometries,
                                        extra_data=entity.extra_data
                                    )
                                ).value
                                entities_updated += 1
                            else:
                                entities_skipped += 1
                        
                        report_lines.append(f"    Layer '{layer.name}' results: {entities_created} created, {entities_updated} updated, {entities_skipped} skipped")
            
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