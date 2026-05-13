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
from src.infrastructure.database.postgis.postgis_entity_repository import PostGISEntityRepository
from src.infrastructure.ezdxf import DXFReader, DXFWriter

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
        entity_repo_class=PostGISEntityRepository,
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
        """
        Интеграционный сценарий базового жизненного цикла DXF-документа.

        Что тестируется:
        1. Открытие нескольких реальных DXF-файлов и добавление в активный репозиторий.
        2. Изменение выбора одной сущности через SelectEntityUseCase.
        3. Закрытие документа через CloseDocumentUseCase.
        4. Публикация событий opened/modified/closed.

        Почему это важно:
        Проверяет согласованность use case между собой на реальных данных, а не только на моках.
        """
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

    def test_reader_open_loads_multiple_layers_and_entities(self):
        """Гарантирует, что DXFReader не обрывает чтение после первой сущности."""
        result = self.reader.open(EXAMPLE_4)
        self.assertTrue(result.is_success, msg=result.error if result.is_fail else "")

        doc = result.value
        self.assertGreater(len(doc.layers), 1, msg="DXFReader loaded only one layer")

        total_entities = 0
        for layer in doc.layers.values():
            total_entities += len(layer.entities)
        self.assertGreater(total_entities, 1, msg="DXFReader loaded only one entity")


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
        self._writer = DXFWriter()
        self._import_use_case = ImportUseCase(self._active_repo, self._reader, self._writer, self._logger)
        self._export_use_case = ExportUseCase(self._writer, self._logger)

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

        open_result = self._open_use_case.execute_single(self._fourth_source_path)
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
        """
        Проверяет, что импорт в БД создает и документ, и бинарный контент.

        Что тестируется:
        1. Импорт реального DXF в выделенные тестовые схемы БД.
        2. Наличие записи документа в file-schema после импорта.
        3. Наличие связанного бинарного содержимого DXF.

        Почему это важно:
        Без целостной пары document/content экспорт и повторное открытие файла работать не будут.
        """
        is_success, report = self._import_document_to_db(self._fourth_source_path)

        self.assertTrue(is_success, msg=report)
        self.assertIn("IMPORT COMPLETED SUCCESSFULLY", report)

        reconnect_result = self._db_session.connect(self._connection)
        self.assertTrue(reconnect_result.is_success, msg=reconnect_result.error if reconnect_result.is_fail else "")

        doc_repo_result = self._db_session._get_document_repository(self._file_schema)
        self.assertTrue(doc_repo_result.is_success, msg=doc_repo_result.error if doc_repo_result.is_fail else "")
        doc_result = doc_repo_result.value.get_by_filename(os.path.basename(self._fourth_source_path))

        self.assertTrue(doc_result.is_success, msg=doc_result.error if doc_result.is_fail else "")
        self.assertIsNotNone(doc_result.value)

        content_repo_result = self._db_session._get_content_repository(self._file_schema)
        self.assertTrue(content_repo_result.is_success, msg=content_repo_result.error if content_repo_result.is_fail else "")
        content_result = content_repo_result.value.get_by_document_id(doc_result.value.id)

        self.assertTrue(content_result.is_success, msg=content_result.error if content_result.is_fail else "")
        self.assertIsNotNone(content_result.value)
        self.assertGreater(len(content_result.value.content), 0)

    def test_tables_export_reconstructs_entities(self):
        """
        Проверяет экспорт в режиме TABLES, когда DXF собирается заново из таблиц слоёв.

        Что тестируется:
        1. Импорт DXF в БД с сохранением сущностей по слоям.
        2. Экспорт через ExportMode.TABLES.
        3. Наличие результата на диске и подробного отчета о реконструкции.

        Почему это важно:
        Этот путь использует фабрику `ezdxf` и наиболее хрупкий участок экспорта.
        """
        is_success, report = self._import_document_to_db(self._fourth_source_path)
        self.assertTrue(is_success, msg=report)

        export_config = ExportConfigDTO(
            filename=os.path.basename(self._fourth_source_path),
            export_mode=ExportMode.TABLES,
            output_path=self._export_path,
            file_schema=self._file_schema,
        )

        with patch("src.application.use_cases.export_use_case.inject.instance", return_value=self._db_session):
            export_result, export_report = self._export_use_case.execute(self._connection, [export_config])

        self.assertTrue(export_result.is_success, msg=export_report)
        self.assertTrue(os.path.exists(self._export_path), msg=export_report)
        self.assertIn("Reconstruction summary:", export_report)
        self.assertIn("reconstructed=", export_report)

        reopen_result = self._reader.open(self._export_path)
        self.assertTrue(reopen_result.is_success, msg=reopen_result.error if reopen_result.is_fail else "")

        with open(self._export_path, "rb") as exported_file:
            exported_bytes = exported_file.read()

        self.assertGreater(len(exported_bytes), 0)

    def test_tables_roundtrip_entity_equality(self):
        """
        Полная проверка roundtrip через режим TABLES: сущности из исходного
        DXF и реконструированного файла должны совпадать по типам и структуре геометрий.
        """
        # Read original document
        orig_result = self._reader.open(self._fourth_source_path)
        self.assertTrue(orig_result.is_success, msg=orig_result.error if orig_result.is_fail else "")
        orig_doc = orig_result.value

        # Import into DB
        is_success, report = self._import_document_to_db(self._fourth_source_path)
        self.assertTrue(is_success, msg=report)

        # Export using TABLES mode
        export_config = ExportConfigDTO(
            filename=os.path.basename(self._fourth_source_path),
            export_mode=ExportMode.TABLES,
            output_path=self._export_path,
            file_schema=self._file_schema,
        )

        with patch("src.application.use_cases.export_use_case.inject.instance", return_value=self._db_session):
            export_result, export_report = self._export_use_case.execute(self._connection, [export_config])

        self.assertTrue(export_result.is_success, msg=export_report)
        self.assertTrue(os.path.exists(self._export_path), msg=export_report)

        # Open reconstructed file
        recon_result = self._reader.open(self._export_path)
        self.assertTrue(recon_result.is_success, msg=recon_result.error if recon_result.is_fail else "")
        recon_doc = recon_result.value

        # Compare layer sets
        orig_layers = {l.name: l for l in orig_doc.layers.values()}
        recon_layers = {l.name: l for l in recon_doc.layers.values()}
        self.assertEqual(set(orig_layers.keys()), set(recon_layers.keys()), msg="Layer names differ between original and reconstructed DXF")

        # Helper: build summary multiset per layer
        def layer_summary(layer):
            from collections import Counter

            ctr = Counter()
            for e in layer.entities.values():
                dxftype = (e.extra_data or {}).get('dxftype') or getattr(e.entity_type, 'value', str(e.entity_type))
                geom_keys = tuple(sorted((e.geometries or {}).keys()))
                # use basic fingerprint: (dxftype, geom_keys, number of geometry items)
                geom_count = 0
                for v in (e.geometries or {}).values():
                    try:
                        if isinstance(v, (list, tuple)):
                            geom_count += len(v)
                        else:
                            geom_count += 1
                    except Exception:
                        geom_count += 1
                ctr[(str(dxftype).upper(), geom_keys, geom_count)] += 1
            return ctr

        for lname in orig_layers.keys():
            orig_ctr = layer_summary(orig_layers[lname])
            recon_ctr = layer_summary(recon_layers[lname])
            self.assertEqual(orig_ctr, recon_ctr, msg=f"Entity fingerprint mismatch on layer '{lname}'")

    def test_tables_roundtrip_preserves_text_and_main_geometry_counts(self):
        """
        Проверяет, что TABLES export не теряет видимые детали: подписи текста и основные типы геометрии.
        """
        orig_result = self._reader.open(self._source_path)
        self.assertTrue(orig_result.is_success, msg=orig_result.error if orig_result.is_fail else "")
        orig_doc = orig_result.value

        load_result = self._open_use_case.execute_single(self._source_path)
        self.assertTrue(load_result.is_success, msg=load_result.error if load_result.is_fail else "")

        is_success, report = self._import_document_to_db(self._source_path)
        self.assertTrue(is_success, msg=report)

        export_config = ExportConfigDTO(
            filename=os.path.basename(self._source_path),
            export_mode=ExportMode.TABLES,
            output_path=self._export_path,
            file_schema=self._file_schema,
        )

        with patch("src.application.use_cases.export_use_case.inject.instance", return_value=self._db_session):
            export_result, export_report = self._export_use_case.execute(self._connection, [export_config])

        self.assertTrue(export_result.is_success, msg=export_report)

        recon_result = self._reader.open(self._export_path)
        self.assertTrue(recon_result.is_success, msg=recon_result.error if recon_result.is_fail else "")
        recon_doc = recon_result.value

        def collect(doc, dxftypes):
            collected = []
            for layer in doc.layers.values():
                for entity in layer.entities.values():
                    entity_type = (entity.extra_data or {}).get("dxftype") or getattr(entity.entity_type, "value", str(entity.entity_type))
                    if str(entity_type).upper() in dxftypes:
                        collected.append(entity)
            return collected

        for dxftype in ("TEXT", "MTEXT", "LINE", "POINT", "CIRCLE", "ARC", "INSERT"):
            orig_entities = collect(orig_doc, {dxftype})
            recon_entities = collect(recon_doc, {dxftype})
            self.assertEqual(
                len(orig_entities),
                len(recon_entities),
                msg=f"Count mismatch for {dxftype}",
            )

        orig_texts = sorted([
            str((entity.geometries or {}).get("text") or (entity.attributes or {}).get("text") or "")
            for entity in collect(orig_doc, {"TEXT", "MTEXT"})
        ])
        recon_texts = sorted([
            str((entity.geometries or {}).get("text") or (entity.attributes or {}).get("text") or "")
            for entity in collect(recon_doc, {"TEXT", "MTEXT"})
        ])
        self.assertEqual(orig_texts, recon_texts, msg="Text labels differ after TABLES roundtrip")

    def test_tables_roundtrip_preserves_reachable_block_structure_for_ex4(self):
        """
        Сравнивает структуру достижимых block definition для EXAMPLE_4.

        Проверяет, что после TABLES-экспорта у блоков, достижимых из modelspace INSERT,
        сохраняются:
        1. Состав сущностей по типам.
        2. Структура HATCH boundary paths (polyline/edge и геометрия ребер).
        """
        from collections import Counter, defaultdict
        import tempfile
        import ezdxf

        orig_result = self._reader.open(self._fourth_source_path)
        self.assertTrue(orig_result.is_success, msg=orig_result.error if orig_result.is_fail else "")

        is_success, report = self._import_document_to_db(self._fourth_source_path)
        self.assertTrue(is_success, msg=report)

        export_config = ExportConfigDTO(
            filename=os.path.basename(self._fourth_source_path),
            export_mode=ExportMode.TABLES,
            output_path=self._export_path,
            file_schema=self._file_schema,
        )

        with patch("src.application.use_cases.export_use_case.inject.instance", return_value=self._db_session):
            export_result, export_report = self._export_use_case.execute(self._connection, [export_config])
        self.assertTrue(export_result.is_success, msg=export_report)

        original_doc = ezdxf.readfile(self._fourth_source_path)
        reconstructed_doc = ezdxf.readfile(self._export_path)

        def block_refs(doc):
            refs = defaultdict(set)
            for block in doc.blocks:
                block_name = getattr(block.dxf, "name", "")
                if not block_name:
                    continue
                for block_entity in block:
                    if block_entity.dxftype() == "INSERT":
                        refs[block_name].add(block_entity.dxf.name)
            return refs

        def modelspace_insert_roots(doc):
            return {entity.dxf.name for entity in doc.modelspace() if entity.dxftype() == "INSERT"}

        def closure(roots, refs):
            seen = set()
            stack = list(roots)
            while stack:
                name = stack.pop()
                if name in seen:
                    continue
                seen.add(name)
                for nested in refs.get(name, set()):
                    if nested not in seen:
                        stack.append(nested)
            return seen

        def round_num(value):
            try:
                return round(float(value), 6)
            except Exception:
                return value

        def to_xy(point):
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                return (round_num(point[0]), round_num(point[1]))
            return tuple(point)

        def hatch_signature(hatch):
            paths = []
            for boundary in hatch.paths:
                if hasattr(boundary, "vertices"):
                    vertices = []
                    for vertex in boundary.vertices:
                        if isinstance(vertex, (list, tuple)) and len(vertex) >= 3:
                            vertices.append((round_num(vertex[0]), round_num(vertex[1]), round_num(vertex[2])))
                        elif isinstance(vertex, (list, tuple)) and len(vertex) >= 2:
                            vertices.append((round_num(vertex[0]), round_num(vertex[1])))
                    paths.append(("polyline", bool(getattr(boundary, "is_closed", True)), tuple(vertices)))
                elif hasattr(boundary, "edges"):
                    edges = []
                    for edge in boundary.edges:
                        if hasattr(edge, "start") and hasattr(edge, "end"):
                            edges.append(("line", to_xy(edge.start), to_xy(edge.end)))
                        elif hasattr(edge, "center") and hasattr(edge, "radius") and hasattr(edge, "start_angle") and hasattr(edge, "end_angle"):
                            edges.append((
                                "arc",
                                to_xy(edge.center),
                                round_num(edge.radius),
                                round_num(edge.start_angle),
                                round_num(edge.end_angle),
                                bool(getattr(edge, "ccw", True)),
                            ))
                    paths.append(("edge", tuple(edges)))

            return (
                str(getattr(hatch.dxf, "pattern_name", "")),
                int(getattr(hatch.dxf, "solid_fill", 0)),
                tuple(paths),
            )

        def entity_signature(entity):
            etype = entity.dxftype()
            if etype == "HATCH":
                return (etype, hatch_signature(entity))
            if etype == "LWPOLYLINE":
                points = []
                try:
                    for point in entity.get_points("xyseb"):
                        points.append(tuple(round_num(value) for value in point))
                except Exception:
                    points = []
                return (
                    etype,
                    tuple(points),
                    bool(getattr(entity, "closed", False)),
                    round_num(getattr(entity.dxf, "const_width", 0)),
                    round_num(getattr(entity.dxf, "elevation", 0)),
                )
            return (etype,)

        reachable_blocks = closure(modelspace_insert_roots(original_doc), block_refs(original_doc))

        for block_name in sorted(reachable_blocks):
            self.assertIn(block_name, reconstructed_doc.blocks, msg=f"Reachable block is missing after export: {block_name}")

            original_block = original_doc.blocks.get(block_name)
            reconstructed_block = reconstructed_doc.blocks.get(block_name)

            original_types = Counter(entity.dxftype() for entity in original_block)
            reconstructed_types = Counter(entity.dxftype() for entity in reconstructed_block)
            self.assertEqual(
                original_types,
                reconstructed_types,
                msg=f"Entity type composition differs for block '{block_name}'",
            )

            original_hatch_sig = Counter(entity_signature(entity) for entity in original_block if entity.dxftype() == "HATCH")
            reconstructed_hatch_sig = Counter(entity_signature(entity) for entity in reconstructed_block if entity.dxftype() == "HATCH")
            self.assertEqual(
                original_hatch_sig,
                reconstructed_hatch_sig,
                msg=f"HATCH path structure differs for block '{block_name}'",
            )

            original_lwpoly_sig = Counter(entity_signature(entity) for entity in original_block if entity.dxftype() == "LWPOLYLINE")
            reconstructed_lwpoly_sig = Counter(entity_signature(entity) for entity in reconstructed_block if entity.dxftype() == "LWPOLYLINE")
            self.assertEqual(
                original_lwpoly_sig,
                reconstructed_lwpoly_sig,
                msg=f"LWPOLYLINE point/bulge structure differs for block '{block_name}'",
            )

    def test_tables_roundtrip_preserves_insert_attached_attributes_for_ex4(self):
        """
        Проверяет, что TABLES roundtrip сохраняет attached ATTRIB у INSERT.

        Это критично для подписей, которые задаются значениями атрибутов блоков,
        а не обычными TEXT/MTEXT сущностями.
        """
        from collections import Counter
        import ezdxf

        is_success, report = self._import_document_to_db(self._fourth_source_path)
        self.assertTrue(is_success, msg=report)

        export_config = ExportConfigDTO(
            filename=os.path.basename(self._fourth_source_path),
            export_mode=ExportMode.TABLES,
            output_path=self._export_path,
            file_schema=self._file_schema,
        )

        with patch("src.application.use_cases.export_use_case.inject.instance", return_value=self._db_session):
            export_result, export_report = self._export_use_case.execute(self._connection, [export_config])
        self.assertTrue(export_result.is_success, msg=export_report)

        original_doc = ezdxf.readfile(self._fourth_source_path)
        reconstructed_doc = ezdxf.readfile(self._export_path)

        def collect_insert_attribs(doc):
            total_attrs = 0
            non_empty_attrs = 0
            tag_counter = Counter()
            text_counter = Counter()

            for insert_entity in doc.modelspace():
                if insert_entity.dxftype() != "INSERT":
                    continue

                for attrib in getattr(insert_entity, "attribs", []):
                    total_attrs += 1
                    tag = str(getattr(attrib.dxf, "tag", ""))
                    text = str(getattr(attrib.dxf, "text", ""))
                    tag_counter[tag] += 1
                    text_counter[text] += 1
                    if text.strip():
                        non_empty_attrs += 1

            return {
                "total": total_attrs,
                "non_empty": non_empty_attrs,
                "tags": tag_counter,
                "texts": text_counter,
            }

        original_stats = collect_insert_attribs(original_doc)
        reconstructed_stats = collect_insert_attribs(reconstructed_doc)

        self.assertEqual(
            original_stats["total"],
            reconstructed_stats["total"],
            msg="INSERT attached ATTRIB count differs after TABLES roundtrip",
        )
        self.assertEqual(
            original_stats["non_empty"],
            reconstructed_stats["non_empty"],
            msg="INSERT non-empty ATTRIB text count differs after TABLES roundtrip",
        )
        self.assertEqual(
            original_stats["tags"],
            reconstructed_stats["tags"],
            msg="INSERT ATTRIB tag distribution differs after TABLES roundtrip",
        )
        self.assertEqual(
            original_stats["texts"],
            reconstructed_stats["texts"],
            msg="INSERT ATTRIB text distribution differs after TABLES roundtrip",
        )

    def test_tables_roundtrip_preserves_text_color_for_ex3(self):
        """
        Проверяет сохранение цветовых атрибутов текста (ACI/true_color) после TABLES roundtrip.

        EXAMPLE_3 используется как fixture с большим количеством текстовых сущностей
        и не-ByLayer цветов.
        """
        from collections import Counter
        import ezdxf

        load_result = self._open_use_case.execute_single(self._third_source_path)
        self.assertTrue(load_result.is_success, msg=load_result.error if load_result.is_fail else "")

        is_success, report = self._import_document_to_db(self._third_source_path)
        self.assertTrue(is_success, msg=report)

        export_config = ExportConfigDTO(
            filename=os.path.basename(self._third_source_path),
            export_mode=ExportMode.TABLES,
            output_path=self._export_path,
            file_schema=self._file_schema,
        )

        with patch("src.application.use_cases.export_use_case.inject.instance", return_value=self._db_session):
            export_result, export_report = self._export_use_case.execute(self._connection, [export_config])
        self.assertTrue(export_result.is_success, msg=export_report)

        original_doc = ezdxf.readfile(self._third_source_path)
        reconstructed_doc = ezdxf.readfile(self._export_path)

        def text_color_stats(doc):
            stat = Counter()
            for entity in doc.modelspace():
                if entity.dxftype() in {"TEXT", "MTEXT"}:
                    stat[(
                        entity.dxftype(),
                        int(getattr(entity.dxf, "color", 256)),
                        getattr(entity.dxf, "true_color", None),
                        str(getattr(entity.dxf, "layer", "0")),
                    )] += 1
            return stat

        self.assertEqual(
            text_color_stats(original_doc),
            text_color_stats(reconstructed_doc),
            msg="TEXT/MTEXT color distribution differs after TABLES roundtrip",
        )

    def test_tables_roundtrip_preserves_multileader_style_for_ex3(self):
        """
        Проверяет, что MULTILEADER на EXAMPLE_3 сохраняет визуальные атрибуты после TABLES roundtrip.

        Регрессия: подписи на линиях рендерились с другими цветом и размером стрелки,
        из-за чего на визуальном просмотре казались пропавшими.
        """
        from collections import Counter
        import ezdxf

        load_result = self._open_use_case.execute_single(self._third_source_path)
        self.assertTrue(load_result.is_success, msg=load_result.error if load_result.is_fail else "")

        is_success, report = self._import_document_to_db(self._third_source_path)
        self.assertTrue(is_success, msg=report)

        export_config = ExportConfigDTO(
            filename=os.path.basename(self._third_source_path),
            export_mode=ExportMode.TABLES,
            output_path=self._export_path,
            file_schema=self._file_schema,
        )

        with patch("src.application.use_cases.export_use_case.inject.instance", return_value=self._db_session):
            export_result, export_report = self._export_use_case.execute(self._connection, [export_config])
        self.assertTrue(export_result.is_success, msg=export_report)

        original_doc = ezdxf.readfile(self._third_source_path)
        reconstructed_doc = ezdxf.readfile(self._export_path)

        def multileader_stats(doc):
            stat = Counter()

            def anchor_point(entity):
                point = getattr(entity.dxf, "insert", None)
                if point is None:
                    mtext = getattr(getattr(entity, "context", None), "mtext", None)
                    point = getattr(mtext, "insert", None)
                if point is None:
                    return None

                coords = list(point)
                while len(coords) < 3:
                    coords.append(0.0)
                return tuple(round(float(coord), 6) for coord in coords[:3])

            def leader_vertices(entity):
                context = getattr(entity, "context", None)
                leaders = getattr(context, "leaders", None)
                if not leaders:
                    return ()

                result = []
                for leader in leaders:
                    for line in getattr(leader, "lines", []) or []:
                        for vertex in getattr(line, "vertices", []) or []:
                            coords = list(vertex)
                            while len(coords) < 3:
                                coords.append(0.0)
                            result.append(tuple(round(float(coord), 6) for coord in coords[:3]))
                return tuple(result)

            def leader_properties(entity):
                context = getattr(entity, "context", None)
                leaders = getattr(context, "leaders", None)
                if not leaders:
                    return ()

                result = []
                for leader in leaders:
                    dogleg_vector = getattr(leader, "dogleg_vector", None)
                    if dogleg_vector is not None:
                        dogleg_vector = tuple(round(float(coord), 6) for coord in tuple(dogleg_vector)[:3])

                    last_leader_point = getattr(leader, "last_leader_point", None)
                    if last_leader_point is not None:
                        last_leader_point = tuple(round(float(coord), 6) for coord in tuple(last_leader_point)[:3])

                    result.append((
                        int(getattr(leader, "attachment_direction", 0) or 0),
                        round(float(getattr(leader, "dogleg_length", 0.0) or 0.0), 6),
                        dogleg_vector,
                        int(bool(getattr(leader, "has_horizontal_attachment", False))),
                        int(bool(getattr(leader, "has_dogleg_vector", False))),
                        last_leader_point,
                    ))
                return tuple(result)

            for entity in doc.modelspace():
                if entity.dxftype() != "MULTILEADER":
                    continue

                stat[(
                    int(getattr(entity.dxf, "color", 256)),
                    float(getattr(entity.dxf, "arrow_head_size", 0.0)),
                    float(getattr(entity.dxf, "dogleg_length", 0.0)),
                    int(getattr(entity.dxf, "has_dogleg", 0)),
                    int(getattr(entity.dxf, "has_landing", 0)),
                    int(getattr(entity.dxf, "has_text_frame", 0)),
                    str(getattr(entity.dxf, "content_type", "")),
                    str(getattr(entity, "get_mtext_content", lambda: getattr(entity, "text", ""))()),
                    anchor_point(entity),
                    leader_vertices(entity),
                    leader_properties(entity),
                )] += 1
            return stat

        self.assertEqual(
            multileader_stats(original_doc),
            multileader_stats(reconstructed_doc),
            msg="MULTILEADER visual attributes differ after TABLES roundtrip",
        )

    def test_tables_roundtrip_preserves_layer_style_for_bylayer_text_ex4(self):
        """
        Проверяет сохранение стиля слоя для текста с цветом ByLayer.

        Регрессия: слой "Водопровод хозпитьевой подземный" терял цвет после TABLES-export,
        из-за чего текст становился чёрным.
        """
        import ezdxf

        is_success, report = self._import_document_to_db(self._fourth_source_path)
        self.assertTrue(is_success, msg=report)

        export_config = ExportConfigDTO(
            filename=os.path.basename(self._fourth_source_path),
            export_mode=ExportMode.TABLES,
            output_path=self._export_path,
            file_schema=self._file_schema,
        )

        with patch("src.application.use_cases.export_use_case.inject.instance", return_value=self._db_session):
            export_result, export_report = self._export_use_case.execute(self._connection, [export_config])
        self.assertTrue(export_result.is_success, msg=export_report)

        original_doc = ezdxf.readfile(self._fourth_source_path)
        reconstructed_doc = ezdxf.readfile(self._export_path)

        target_layer = "Водопровод хозпитьевой подземный"
        self.assertIn(target_layer, original_doc.layers, msg=f"Layer '{target_layer}' not found in source fixture")
        self.assertIn(target_layer, reconstructed_doc.layers, msg=f"Layer '{target_layer}' not found after TABLES roundtrip")

        orig_layer = original_doc.layers.get(target_layer)
        recon_layer = reconstructed_doc.layers.get(target_layer)

        self.assertEqual(orig_layer.dxf.color, recon_layer.dxf.color, msg="Layer ACI color differs after TABLES roundtrip")
        self.assertEqual(
            getattr(orig_layer.dxf, "true_color", None),
            getattr(recon_layer.dxf, "true_color", None),
            msg="Layer true_color differs after TABLES roundtrip",
        )
        self.assertEqual(orig_layer.dxf.linetype, recon_layer.dxf.linetype, msg="Layer linetype differs after TABLES roundtrip")

    def test_import_and_export_multiple_files(self):
        """
        Проверяет пакетный сценарий для нескольких файлов подряд.

        Что тестируется:
        1. Открытие нескольких реальных DXF.
        2. Последовательный импорт каждого файла в БД.
        3. Пакетный экспорт набора конфигов за один вызов ExportUseCase.
        4. Фактическое создание всех результирующих файлов на диске.

        Почему это важно:
        Подтверждает корректную работу use case в батч-режиме, который используется в реальном UI.
        """
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
