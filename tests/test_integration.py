# -*- coding: utf-8 -*-
"""Integration tests for refactored workflows with real implementations."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

plugin_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if plugin_path not in sys.path:
    sys.path.insert(0, plugin_path)

from src.application.database import DBSession
from src.application.dtos import ConnectionConfigDTO, ExportConfigDTO, ExportMode, ImportConfigDTO, ImportMode
from src.application.events import IAppEvents, IEvent
from src.application.interfaces import ILogger
from src.application.results import AppResult
from src.application.use_cases import (
    CloseDocumentUseCase,
    ExportUseCase,
    ImportUseCase,
    OpenDocumentUseCase,
    SelectEntityUseCase,
)
from src.domain.entities import DXFContent
from src.domain.services import IDXFWriter
from src.infrastructure.database import ActiveDocumentRepository, ConnectionFactory, RepositoryFactory
from src.infrastructure.database.postgis.postgis_connection import PostGISConnection
from src.infrastructure.database.postgis.postgis_content_repository import PostGISContentRepository
from src.infrastructure.database.postgis.postgis_document_repository import PostGISDocumentRepository
from src.infrastructure.database.postgis.postgis_layer_repository import PostGISLayerRepository
from src.infrastructure.ezdxf import DXFReader

EXAMPLES_DIR = os.path.join(plugin_path, "dxf_examples")
EXAMPLE_1 = os.path.join(EXAMPLES_DIR, "ex1.dxf")
EXAMPLE_2 = os.path.join(EXAMPLES_DIR, "ex2.dxf")
EXAMPLE_3 = os.path.join(EXAMPLES_DIR, "ex3.dxf")
EXAMPLE_4 = os.path.join(EXAMPLES_DIR, "ex4.dxf")


def _create_logger() -> ILogger:
    logger = MagicMock(spec=ILogger)
    logger.is_enabled.return_value = True
    return logger


def _create_app_events() -> IAppEvents:
    events = MagicMock(spec=IAppEvents)
    events.on_document_opened = MagicMock(spec=IEvent)
    events.on_document_saved = MagicMock(spec=IEvent)
    events.on_document_closed = MagicMock(spec=IEvent)
    events.on_document_modified = MagicMock(spec=IEvent)
    events.on_language_changed = MagicMock(spec=IEvent)
    return events


def _get_test_db_config() -> ConnectionConfigDTO:
    return ConnectionConfigDTO(
        db_type=os.environ.get("TEST_DB_TYPE", "PostgreSQL/PostGIS"),
        name=os.environ.get("TEST_DB_NAME_ALIAS", "integration-test"),
        host=os.environ.get("TEST_DB_HOST", "localhost"),
        port=os.environ.get("TEST_DB_PORT", "5432"),
        database=os.environ.get("TEST_DB_NAME", "test_dxf"),
        username=os.environ.get("TEST_DB_USER", "postgres"),
        password=os.environ.get("TEST_DB_PASSWORD", "123"),
    )


def _build_db_session(logger: ILogger) -> DBSession:
    connection_factory = ConnectionFactory([PostGISConnection])
    repository_factory = RepositoryFactory()
    repository_factory.register_repositories(
        connection_type=PostGISConnection,
        document_repo_class=PostGISDocumentRepository,
        layer_repo_class=PostGISLayerRepository,
        content_repo_class=PostGISContentRepository,
    )
    return DBSession(connection_factory, repository_factory, logger)


class TestCoreWorkflowIntegration(unittest.TestCase):
    def setUp(self):
        self.repo = ActiveDocumentRepository()
        self.events = _create_app_events()
        self.logger = _create_logger()
        self.reader = DXFReader()
        self.writer = MagicMock(spec=IDXFWriter)
        self._source_paths = [EXAMPLE_1, EXAMPLE_2, EXAMPLE_3, EXAMPLE_4]

        if any(not os.path.exists(path) for path in self._source_paths):
            raise unittest.SkipTest("Required fixture files are missing in dxf_examples")

        self.open_use_case = OpenDocumentUseCase(self.repo, self.reader, self.events, self.logger)
        self.select_use_case = SelectEntityUseCase(self.repo, self.events, self.logger)
        self.close_use_case = CloseDocumentUseCase(self.repo, self.writer, self.events)

    def test_open_select_close_workflow(self):
        open_result = self.open_use_case.execute(self._source_paths)
        self.assertTrue(open_result.is_success)
        self.assertEqual(len(open_result.value), 4)
        self.events.on_document_opened.emit.assert_called_once()

        docs_result = self.repo.get_all()
        self.assertTrue(docs_result.is_success)
        self.assertEqual(len(docs_result.value), 4)

        first_doc = docs_result.value[0]
        first_layer = next(iter(first_doc.layers.values()))
        first_entity = next(iter(first_layer.entities.values()))

        select_result = self.select_use_case.execute({first_entity.id: False})
        self.assertTrue(select_result.is_success)
        self.events.on_document_modified.emit.assert_called_once()

        close_result = self.close_use_case.execute(first_doc.id)
        self.assertTrue(close_result.is_success)
        self.events.on_document_closed.emit.assert_called_once_with(first_doc.id)


class TestDbImportExportIntegration(unittest.TestCase):
    """Real DB integration tests for import/export and DXF roundtrip."""

    @classmethod
    def setUpClass(cls):
        cls._logger = _create_logger()
        cls._connection = _get_test_db_config()

        probe = _build_db_session(cls._logger)
        probe_result = probe.connect(cls._connection)
        probe.close()
        if probe_result.is_fail:
            raise unittest.SkipTest(f"Test database is not available: {probe_result.error}")

    def setUp(self):
        self._logger = _create_logger()
        self._events = _create_app_events()
        self._active_repo = ActiveDocumentRepository()

        self._db_session = _build_db_session(self._logger)
        self._file_schema = f"test_file_{uuid4().hex[:8]}"
        self._layer_schema = f"test_layer_{uuid4().hex[:8]}"

        connect_result = self._db_session.connect(self._connection)
        if connect_result.is_fail:
            self.fail(f"Cannot connect to test database in setUp: {connect_result.error}")

        file_schema_result = self._db_session.create_schema(self._file_schema)
        if file_schema_result.is_fail:
            self.fail(f"Cannot create file schema '{self._file_schema}': {file_schema_result.error}")

        layer_schema_result = self._db_session.create_schema(self._layer_schema)
        if layer_schema_result.is_fail:
            self.fail(f"Cannot create layer schema '{self._layer_schema}': {layer_schema_result.error}")

        self._db_session.close()

        self._reader = DXFReader()
        self._open_use_case = OpenDocumentUseCase(self._active_repo, self._reader, self._events, self._logger)
        self._import_use_case = ImportUseCase(self._active_repo, self._logger)
        self._export_use_case = ExportUseCase(self._logger)

        if any(not os.path.exists(path) for path in [EXAMPLE_1, EXAMPLE_2, EXAMPLE_3, EXAMPLE_4]):
            raise unittest.SkipTest("Required fixture files are missing in dxf_examples")

        self._source_path = EXAMPLE_1
        self._second_source_path = EXAMPLE_2
        self._third_source_path = EXAMPLE_3
        self._fourth_source_path = EXAMPLE_4
        self._tmp_export_dir = os.path.join(plugin_path, "tests", "_tmp_exports")
        os.makedirs(self._tmp_export_dir, exist_ok=True)
        self._export_path = os.path.join(self._tmp_export_dir, f"exported_{uuid4().hex[:8]}.dxf")
        self._second_export_path = os.path.join(self._tmp_export_dir, f"exported_{uuid4().hex[:8]}_second.dxf")
        self._third_export_path = os.path.join(self._tmp_export_dir, f"exported_{uuid4().hex[:8]}_third.dxf")
        self._fourth_export_path = os.path.join(self._tmp_export_dir, f"exported_{uuid4().hex[:8]}_fourth.dxf")

        open_result = self._open_use_case.execute_single(self._source_path)
        if open_result.is_fail:
            self.fail(f"Failed to open generated DXF fixture: {open_result.error}")

    def tearDown(self):
        for schema_name in [self._file_schema, self._layer_schema]:
            self._drop_schema(schema_name)

        self._db_session.close()
        for path in [self._export_path, self._second_export_path, self._third_export_path, self._fourth_export_path]:
            if os.path.exists(path):
                os.remove(path)

    def _drop_schema(self, schema_name: str):
        connect_result = self._db_session.connect(self._connection)
        if connect_result.is_fail or not self._db_session._connection:
            return

        try:
            self._db_session._connection.drop_schema(schema_name, cascade=True)
        finally:
            self._db_session.close()

    def _import_document_to_db(self, source_path: str) -> tuple[bool, str]:
        filename = os.path.basename(source_path)

        # Seed DB with the current document and content so ImportUseCase can run update flow.
        seed_result = self._seed_document_and_content(source_path)
        if seed_result.is_fail:
            return False, seed_result.error

        import_config = ImportConfigDTO(
            filename=filename,
            import_mode=ImportMode.ADD_OBJECTS,
            layer_schema=self._layer_schema,
            file_schema=self._file_schema,
            import_layers_only=False,
        )

        with patch("src.application.use_cases.import_use_case.inject.instance", return_value=self._db_session):
            result, report = self._import_use_case.execute(self._connection, [import_config])

        return result.is_success, report

    def _seed_document_and_content(self, source_path: str) -> AppResult[dict]:
        filename = os.path.basename(source_path)
        open_result = self._reader.open(source_path)
        if open_result.is_fail:
            return AppResult.fail(f"DXF read failed: {open_result.error}")

        document = open_result.value

        connect_result = self._db_session.connect(self._connection)
        if connect_result.is_fail:
            return AppResult.fail(f"DB connect failed: {connect_result.error}")

        try:
            doc_repo_result = self._db_session._get_document_repository(self._file_schema)
            if doc_repo_result.is_fail:
                return AppResult.fail(f"Document repository failed: {doc_repo_result.error}")

            content_repo_result = self._db_session._get_content_repository(self._file_schema)
            if content_repo_result.is_fail:
                return AppResult.fail(f"Content repository failed: {content_repo_result.error}")

            doc_repo = doc_repo_result.value
            content_repo = content_repo_result.value

            exists_result = doc_repo.exists(filename)
            if exists_result.is_fail:
                return AppResult.fail(f"Document exists check failed: {exists_result.error}")

            if exists_result.value:
                save_doc_result = doc_repo.update(document)
            else:
                save_doc_result = doc_repo.create(document)

            if save_doc_result.is_fail:
                rollback_result = self._db_session.rollback()
                rollback_msg = rollback_result.error if rollback_result.is_fail else ""
                return AppResult.fail(f"Document save failed: {save_doc_result.error}. {rollback_msg}")

            saved_document = save_doc_result.value
            existing_content_result = content_repo.get_by_document_id(saved_document.id)

            if existing_content_result.is_success and existing_content_result.value is not None:
                content_result = content_repo.update(
                    DXFContent.create(
                        id=existing_content_result.value.id,
                        document_id=saved_document.id,
                        content=document.content.content,
                    )
                )
                saved_content = existing_content_result.value
            else:
                content_result = content_repo.create(
                    DXFContent.create(document_id=saved_document.id, content=document.content.content)
                )
                saved_content = content_result.value if content_result.is_success else None

            if content_result.is_fail:
                rollback_result = self._db_session.rollback()
                rollback_msg = rollback_result.error if rollback_result.is_fail else ""
                return AppResult.fail(f"Content save failed: {content_result.error}. {rollback_msg}")

            commit_result = self._db_session.commit()
            if commit_result.is_fail:
                rollback_result = self._db_session.rollback()
                rollback_msg = rollback_result.error if rollback_result.is_fail else ""
                return AppResult.fail(f"Commit failed: {commit_result.error}. {rollback_msg}")

            if saved_content is None:
                loaded_content_result = content_repo.get_by_document_id(saved_document.id)
                if loaded_content_result.is_fail or loaded_content_result.value is None:
                    return AppResult.fail("Failed to load saved content for import use case")
                saved_content = loaded_content_result.value

            return AppResult.success({"document": saved_document, "content": saved_content})
        finally:
            self._db_session.close()

    def test_import_to_db_creates_document_and_content(self):
        is_success, report = self._import_document_to_db(self._source_path)

        self.assertTrue(is_success, msg=report)
        self.assertIn("IMPORT COMPLETED SUCCESSFULLY", report)

        reconnect_result = self._db_session.connect(self._connection)
        self.assertTrue(reconnect_result.is_success, msg=reconnect_result.error if reconnect_result.is_fail else "")

        doc_repo_result = self._db_session._get_document_repository(self._file_schema)
        self.assertTrue(doc_repo_result.is_success, msg=doc_repo_result.error if doc_repo_result.is_fail else "")
        doc_result = doc_repo_result.value.get_by_filename(os.path.basename(self._source_path))

        self.assertTrue(doc_result.is_success, msg=doc_result.error if doc_result.is_fail else "")
        self.assertIsNotNone(doc_result.value)

        content_repo_result = self._db_session._get_content_repository(self._file_schema)
        self.assertTrue(content_repo_result.is_success, msg=content_repo_result.error if content_repo_result.is_fail else "")
        content_result = content_repo_result.value.get_by_document_id(doc_result.value.id)

        self.assertTrue(content_result.is_success, msg=content_result.error if content_result.is_fail else "")
        self.assertIsNotNone(content_result.value)
        self.assertGreater(len(content_result.value.content), 0)

    def test_roundtrip_db_to_dxf_preserves_content(self):
        is_success, report = self._import_document_to_db(self._source_path)
        self.assertTrue(is_success, msg=report)

        export_config = ExportConfigDTO(
            filename=os.path.basename(self._source_path),
            export_mode=ExportMode.FILE,
            output_path=self._export_path,
            file_schema=self._file_schema,
        )

        with patch("src.application.use_cases.export_use_case.inject.instance", return_value=self._db_session):
            export_result, export_report = self._export_use_case.execute(self._connection, [export_config])

        self.assertTrue(export_result.is_success, msg=export_report)
        self.assertTrue(os.path.exists(self._export_path))
        self.assertIn("EXPORT COMPLETED SUCCESSFULLY", export_report)

        reopen_result = self._reader.open(self._export_path)
        self.assertTrue(reopen_result.is_success, msg=reopen_result.error if reopen_result.is_fail else "")

        with open(self._source_path, "rb") as source_file:
            source_bytes = source_file.read()
        with open(self._export_path, "rb") as exported_file:
            exported_bytes = exported_file.read()

        self.assertEqual(source_bytes, exported_bytes)

    def test_import_and_export_multiple_files(self):
        open_result = self._open_use_case.execute([
            self._source_path,
            self._second_source_path,
            self._third_source_path,
            self._fourth_source_path,
        ])
        self.assertTrue(open_result.is_success, msg=open_result.error if open_result.is_fail else "")

        first_import_success, first_report = self._import_document_to_db(self._source_path)
        self.assertTrue(first_import_success, msg=first_report)

        second_import_success, second_report = self._import_document_to_db(self._second_source_path)
        self.assertTrue(second_import_success, msg=second_report)

        third_import_success, third_report = self._import_document_to_db(self._third_source_path)
        self.assertTrue(third_import_success, msg=third_report)

        fourth_import_success, fourth_report = self._import_document_to_db(self._fourth_source_path)
        self.assertTrue(fourth_import_success, msg=fourth_report)

        export_configs = [
            ExportConfigDTO(
                filename=os.path.basename(self._source_path),
                export_mode=ExportMode.FILE,
                output_path=self._export_path,
                file_schema=self._file_schema,
            ),
            ExportConfigDTO(
                filename=os.path.basename(self._second_source_path),
                export_mode=ExportMode.FILE,
                output_path=self._second_export_path,
                file_schema=self._file_schema,
            ),
            ExportConfigDTO(
                filename=os.path.basename(self._third_source_path),
                export_mode=ExportMode.FILE,
                output_path=self._third_export_path,
                file_schema=self._file_schema,
            ),
            ExportConfigDTO(
                filename=os.path.basename(self._fourth_source_path),
                export_mode=ExportMode.FILE,
                output_path=self._fourth_export_path,
                file_schema=self._file_schema,
            ),
        ]

        with patch("src.application.use_cases.export_use_case.inject.instance", return_value=self._db_session):
            export_result, export_report = self._export_use_case.execute(self._connection, export_configs)

        self.assertTrue(export_result.is_success, msg=export_report)
        self.assertTrue(os.path.exists(self._export_path))
        self.assertTrue(os.path.exists(self._second_export_path))
        self.assertTrue(os.path.exists(self._third_export_path))
        self.assertTrue(os.path.exists(self._fourth_export_path))


if __name__ == "__main__":
    unittest.main(verbosity=2)
