# -*- coding: utf-8 -*-
"""Unit tests for services and use cases in the new implementation."""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.application.interfaces import ILogger

plugin_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if plugin_path not in sys.path:
    sys.path.insert(0, plugin_path)

from src.application.dtos import (
    ConnectionConfigDTO,
    ExportConfigDTO,
    ExportMode,
    ImportConfigDTO,
    ImportMode,
)
from src.application.results import AppResult, Unit
from src.application.services import ConnectionConfigService
from src.application.use_cases import ExportUseCase, ImportUseCase, OpenDocumentUseCase, SelectEntityUseCase
from src.domain.entities import DXFContent, DXFDocument, DXFEntity, DXFLayer
from src.domain.value_objects import DxfEntityType


class _DummyEvent:
    def __init__(self):
        self.emitted = []

    def emit(self, payload):
        self.emitted.append(payload)


class _DummyAppEvents:
    def __init__(self):
        self.on_document_opened = _DummyEvent()
        self.on_document_saved = _DummyEvent()
        self.on_document_closed = _DummyEvent()
        self.on_document_modified = _DummyEvent()
        self.on_language_changed = _DummyEvent()


class _DummyLogger(ILogger):
    def is_enabled(self) -> bool:
        return True

    def set_enabled(self, enabled: bool):
        return None

    def message(self, message, tag="DXF-PostGIS-Converter"):
        return None

    def warning(self, message, tag="DXF-PostGIS-Converter"):
        return None

    def error(self, message, tag="DXF-PostGIS-Converter"):
        return None


class TestConnectionConfigService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.logger = _DummyLogger()
        self.connection_factory = MagicMock()
        self.connection_factory.get_supported_databases.return_value = ["postgis", "sqlite"]

        self.service = ConnectionConfigService(
            plugin_dir=self.temp_dir.name,
            connection_factory=self.connection_factory,
            logger=self.logger,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_creates_connections_file_on_init(self):
        path = os.path.join(self.temp_dir.name, "connections.json")
        self.assertTrue(os.path.exists(path))

    def test_save_and_get_config_roundtrip(self):
        config = ConnectionConfigDTO(
            db_type="postgis",
            name="local",
            host="localhost",
            port="5432",
            database="dxf",
            username="postgres",
            password="secret",
        )

        result = self.service.save_config(config)

        self.assertTrue(result.is_success)
        loaded = self.service.get_config_by_name("local")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.host, "localhost")
        self.assertEqual(loaded.database, "dxf")

    def test_delete_config(self):
        config = ConnectionConfigDTO(
            db_type="postgis",
            name="to-delete",
            host="localhost",
            port="5432",
            database="dxf",
            username="postgres",
            password="secret",
        )
        self.service.save_config(config)

        delete_result = self.service.delete_config("to-delete")

        self.assertTrue(delete_result.is_success)
        self.assertIsNone(self.service.get_config_by_name("to-delete"))


class TestOpenDocumentUseCase(unittest.TestCase):
    def setUp(self):
        self.active_repo = MagicMock()
        self.reader = MagicMock()
        self.events = _DummyAppEvents()
        self.logger = _DummyLogger()
        self.use_case = OpenDocumentUseCase(self.active_repo, self.reader, self.events, self.logger)

    def test_execute_fails_when_no_files_provided(self):
        result = self.use_case.execute([])

        self.assertTrue(result.is_fail)
        self.assertIn("No files", result.error)

    def test_execute_success_emits_event(self):
        doc = DXFDocument(filename="sample.dxf", filepath="C:/tmp/sample.dxf")
        self.reader.open.return_value = AppResult.success(doc)
        self.active_repo.create.return_value = AppResult.success(doc)

        result = self.use_case.execute(["C:/tmp/sample.dxf"])

        self.assertTrue(result.is_success)
        self.assertEqual(len(result.value), 1)
        self.assertEqual(len(self.events.on_document_opened.emitted), 1)


class TestSelectEntityUseCase(unittest.TestCase):
    def setUp(self):
        self.active_repo = MagicMock()
        self.events = _DummyAppEvents()
        self.logger = _DummyLogger()
        self.use_case = SelectEntityUseCase(self.active_repo, self.events, self.logger)

        self.document = DXFDocument(filename="doc.dxf", filepath="/tmp/doc.dxf")
        layer = DXFLayer(
            document_id=self.document.id,
            name="L1",
            schema_name="layer_schema",
            table_name="l1",
        )
        self.entity = DXFEntity(entity_type=DxfEntityType.LINE, name="line-1")
        layer.add_entities([self.entity])
        self.document.add_layers([layer])

    def test_execute_updates_entity_selection_and_emits(self):
        self.active_repo.get_all.return_value = AppResult.success([self.document])
        self.active_repo.update.return_value = AppResult.success(self.document)

        result = self.use_case.execute({self.entity.id: False})

        self.assertTrue(result.is_success)
        self.assertFalse(self.entity.is_selected)
        self.assertEqual(self.active_repo.update.call_count, 1)
        self.assertEqual(len(self.events.on_document_modified.emitted), 1)


class TestImportUseCase(unittest.TestCase):
    def setUp(self):
        self.active_repo = MagicMock()
        self.logger = _DummyLogger()
        self.use_case = ImportUseCase(self.active_repo, self.logger)

        self.connection = ConnectionConfigDTO(
            db_type="postgis",
            name="local",
            host="localhost",
            port="5432",
            database="dxf",
            username="postgres",
            password="secret",
        )

    def test_execute_fails_without_connection(self):
        result, report = self.use_case.execute(None, [])

        self.assertTrue(result.is_fail)
        self.assertIn("No connection", result.error)
        self.assertIn("Starting DXF import process", report)

    def test_execute_fails_when_document_not_found(self):
        config = ImportConfigDTO(
            filename="missing.dxf",
            import_mode=ImportMode.ADD_OBJECTS,
            layer_schema="layer_schema",
            file_schema="file_schema",
            import_layers_only=True,
        )
        self.active_repo.get_by_filename.return_value = AppResult.fail("not found")

        fake_session = MagicMock()
        with patch("src.application.use_cases.import_use_case.inject.instance", return_value=fake_session):
            result, report = self.use_case.execute(self.connection, [config])

        self.assertTrue(result.is_fail)
        self.assertIn("not found", report)

    def test_execute_success_for_layers_only_path(self):
        doc = DXFDocument(filename="ok.dxf", filepath="C:/tmp/ok.dxf")
        doc.add_content(DXFContent(document_id=doc.id, content=b"0\nEOF\n"))

        config = ImportConfigDTO(
            filename="ok.dxf",
            import_mode=ImportMode.ADD_OBJECTS,
            layer_schema="layer_schema",
            file_schema="file_schema",
            import_layers_only=True,
        )

        self.active_repo.get_by_filename.return_value = AppResult.success(doc)

        fake_session = MagicMock()
        fake_session.connect.return_value = AppResult.success(Unit())
        fake_session.schema_exists.return_value = AppResult.success(True)

        with patch("src.application.use_cases.import_use_case.inject.instance", return_value=fake_session):
            result, report = self.use_case.execute(self.connection, [config])

        self.assertTrue(result.is_success)
        self.assertIn("IMPORT COMPLETED SUCCESSFULLY", report)
        fake_session.commit.assert_called_once()
        fake_session.close.assert_called_once()


class TestExportUseCase(unittest.TestCase):
    def setUp(self):
        self.logger = _DummyLogger()
        self.use_case = ExportUseCase(self.logger)

        self.connection = ConnectionConfigDTO(
            db_type="postgis",
            name="local",
            host="localhost",
            port="5432",
            database="dxf",
            username="postgres",
            password="secret",
        )

    def test_execute_fails_without_configs(self):
        result, report = self.use_case.execute(self.connection, [])

        self.assertTrue(result.is_fail)
        self.assertIn("No configs", result.error)
        self.assertIn("Starting DXF export process", report)

    def test_execute_writes_output_file(self):
        document_id = uuid4()
        document = DXFDocument(id=document_id, filename="from_db.dxf", filepath="")
        content = DXFContent(document_id=document_id, content=b"0\nEOF\n")

        doc_repo = MagicMock()
        doc_repo.get_by_filename.return_value = AppResult.success(document)

        content_repo = MagicMock()
        content_repo.get_by_document_id.return_value = AppResult.success(content)

        fake_session = MagicMock()
        fake_session.connect.return_value = AppResult.success(Unit())
        fake_session.schema_exists.return_value = AppResult.success(True)
        fake_session._get_document_repository.return_value = AppResult.success(doc_repo)
        fake_session._get_content_repository.return_value = AppResult.success(content_repo)

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = os.path.join(tmp_dir, "result.dxf")
            config = ExportConfigDTO(
                filename="from_db.dxf",
                export_mode=ExportMode.FILE,
                output_path=out_path,
                file_schema="file_schema",
            )

            with patch("src.application.use_cases.export_use_case.inject.instance", return_value=fake_session):
                result, report = self.use_case.execute(self.connection, [config])

            self.assertTrue(result.is_success)
            self.assertTrue(os.path.exists(out_path))
            self.assertIn("EXPORT COMPLETED SUCCESSFULLY", report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
