# -*- coding: utf-8 -*-
"""Debug smoke tests for import/export reports in the new implementation."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

plugin_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if plugin_path not in sys.path:
    sys.path.insert(0, plugin_path)

from src.application.interfaces import ILogger
from src.application.dtos import ConnectionConfigDTO, ExportConfigDTO, ExportMode, ImportConfigDTO, ImportMode
from src.application.results import AppResult, Unit
from src.application.use_cases import ExportUseCase, ImportUseCase
from src.domain.entities import DXFContent, DXFDocument


class _Logger(ILogger):
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


class TestDebugReports(unittest.TestCase):
    def setUp(self):
        self.connection = ConnectionConfigDTO(
            db_type="postgis",
            name="debug",
            host="localhost",
            port="5432",
            database="dxf",
            username="postgres",
            password="secret",
        )

    def test_import_report_contains_pipeline_steps(self):
        """
        Проверяет, что отчет ImportUseCase содержит ключевые этапы пайплайна.

        Что тестируется:
        1. Импорт завершается успешно на мок-сессии БД.
        2. Текстовый отчет содержит стартовую запись процесса.
        3. Текстовый отчет содержит финальный маркер успешного завершения.

        Почему это важно:
        Отчет используется для диагностики и должен быть информативным даже при smoke-проверках.
        """
        active_repo = MagicMock()
        logger = _Logger()
        dxf_reader = MagicMock()
        dxf_reader.save_svg_preview.return_value = AppResult.success("preview.svg")
        use_case = ImportUseCase(active_repo, dxf_reader, logger)

        doc = DXFDocument(filename="debug.dxf", filepath="C:/tmp/debug.dxf")
        doc.add_content(DXFContent(document_id=doc.id, content=b"0\nEOF\n"))
        active_repo.get_by_filename.return_value = AppResult.success(doc)

        fake_session = MagicMock()
        fake_session.connect.return_value = AppResult.success(Unit())
        fake_session.schema_exists.return_value = AppResult.success(True)

        config = ImportConfigDTO(
            filename="debug.dxf",
            import_mode=ImportMode.ADD_OBJECTS,
            layer_schema="layer_schema",
            file_schema="file_schema",
            import_layers_only=True,
        )

        with patch("src.application.use_cases.import_use_case.inject.instance", return_value=fake_session):
            result, report = use_case.execute(self.connection, [config])

        self.assertTrue(result.is_success)
        self.assertIn("Starting DXF import process", report)
        self.assertIn("IMPORT COMPLETED SUCCESSFULLY", report)

    def test_export_report_contains_success_footer(self):
        """
        Проверяет, что отчет ExportUseCase содержит итоговый success-footer.

        Что тестируется:
        1. Экспорт завершается успешно при корректных данных из репозиториев.
        2. В отчете присутствует строка об успешном завершении экспорта.

        Почему это важно:
        Этот маркер нужен для быстрой проверки результата экспорта в debug-режиме и логах.
        """
        logger = _Logger()
        use_case = ExportUseCase(logger)

        document_id = uuid4()
        document = DXFDocument(id=document_id, filename="debug.dxf", filepath="")
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

        out_path = os.path.join(os.path.dirname(__file__), "_debug_export.dxf")
        try:
            config = ExportConfigDTO(
                filename="debug.dxf",
                export_mode=ExportMode.FILE,
                output_path=out_path,
                file_schema="file_schema",
            )

            with patch("src.application.use_cases.export_use_case.inject.instance", return_value=fake_session):
                result, report = use_case.execute(self.connection, [config])

            self.assertTrue(result.is_success)
            self.assertIn("EXPORT COMPLETED SUCCESSFULLY", report)
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
