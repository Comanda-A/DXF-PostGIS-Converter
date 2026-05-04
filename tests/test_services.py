# -*- coding: utf-8 -*-
"""Unit tests for services and use cases in the new implementation."""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

plugin_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if plugin_path not in sys.path:
    sys.path.insert(0, plugin_path)

from src.application.dtos import (
    AreaSelectionRequestDTO,
    ConnectionConfigDTO,
    ExportConfigDTO,
    ExportMode,
    ImportConfigDTO,
    ImportMode,
    SelectionMode,
    SelectionRule,
    ShapeType,
)
from src.application.interfaces import ILogger
from src.application.results import AppResult, Unit
from src.application.services import ConnectionConfigService
from src.application.use_cases import (
    CloseDocumentUseCase,
    DataViewerUseCase,
    ExportUseCase,
    ImportUseCase,
    OpenDocumentUseCase,
    SaveSelectedToFileUseCase,
    SelectAreaUseCase,
    SelectEntityUseCase,
)
from src.domain.entities import DXFContent, DXFDocument, DXFEntity, DXFLayer
from src.domain.value_objects import (
    DxfEntityType,
)
from src.infrastructure.database import ActiveDocumentRepository
from src.infrastructure.ezdxf import DXFReader, DXFWriter

EXAMPLES_DIR = os.path.join(plugin_path, "dxf_examples")
EXAMPLE_1 = os.path.join(EXAMPLES_DIR, "ex1.dxf")
EXAMPLE_2 = os.path.join(EXAMPLES_DIR, "ex2.dxf")
EXAMPLE_3 = os.path.join(EXAMPLES_DIR, "ex3.dxf")
EXAMPLE_4 = os.path.join(EXAMPLES_DIR, "ex4.dxf")


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
        """
        Проверяет автоинициализацию файла конфигураций подключений.

        Что тестируется:
        1. При создании ConnectionConfigService в рабочей директории появляется connections.json.

        Почему это важно:
        Сервис должен быть готов к работе "из коробки" без ручного создания файла.
        """
        path = os.path.join(self.temp_dir.name, "connections.json")
        self.assertTrue(os.path.exists(path))

    def test_save_and_get_config_roundtrip(self):
        """
        Проверяет сохранение и последующее чтение конфигурации подключения.

        Что тестируется:
        1. save_config успешно сохраняет DTO в storage.
        2. get_config_by_name возвращает ту же конфигурацию.
        3. Критичные поля (host, database) сохранены без искажений.

        Почему это важно:
        Ошибки здесь ломают дальнейшие операции импорта/экспорта через БД.
        """
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
        """
        Проверяет удаление сохраненной конфигурации подключения.

        Что тестируется:
        1. После delete_config запись больше не находится по имени.
        2. Операция удаления завершается успешно.

        Почему это важно:
        UI-редактор подключений должен надежно удалять устаревшие конфиги.
        """
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
        """
        Проверяет валидацию входных данных OpenDocumentUseCase.

        Что тестируется:
        1. При пустом списке путей use case возвращает fail.
        2. Сообщение ошибки содержит указание на отсутствие файлов.

        Почему это важно:
        Ранняя валидация предотвращает лишние вызовы reader/repository.
        """
        result = self.use_case.execute([])

        self.assertTrue(result.is_fail)
        self.assertIn("No files", result.error)

    def test_execute_success_emits_event(self):
        """
        Проверяет успешное открытие одного файла и отправку события.

        Что тестируется:
        1. Reader возвращает документ, repository успешно сохраняет его.
        2. Use case возвращает success с одним DTO.
        3. Событие on_document_opened отправлено один раз.

        Почему это важно:
        UI строит дерево документов именно на основе этого события.
        """
        doc = DXFDocument(filename="sample.dxf", filepath="C:/tmp/sample.dxf")
        self.reader.open.return_value = AppResult.success(doc)
        self.active_repo.create.return_value = AppResult.success(doc)

        result = self.use_case.execute(["C:/tmp/sample.dxf"])

        self.assertTrue(result.is_success)
        self.assertEqual(len(result.value), 1)
        self.assertEqual(len(self.events.on_document_opened.emitted), 1)

    def test_execute_single_with_real_fixture_file(self):
        """
        Проверяет execute_single на реальных DXF-файлах фикстур.

        Что тестируется:
        1. Каждый реальный файл открывается без ошибок через DXFReader.
        2. Имя файла в DTO совпадает с именем входного fixture-файла.

        Почему это важно:
        Гарантирует совместимость парсинга с реальными образцами DXF из проекта.
        """
        fixture_paths = [EXAMPLE_1, EXAMPLE_2, EXAMPLE_3, EXAMPLE_4]
        if any(not os.path.exists(path) for path in fixture_paths):
            self.skipTest("One or more fixture files are missing in dxf_examples")

        active_repo = ActiveDocumentRepository()
        reader = DXFReader()
        use_case = OpenDocumentUseCase(active_repo, reader, self.events, self.logger)

        for fixture_path in fixture_paths:
            with self.subTest(fixture=os.path.basename(fixture_path)):
                result = use_case.execute_single(fixture_path)

                self.assertTrue(result.is_success, msg=result.error if result.is_fail else "")
                self.assertEqual(result.value.filename, os.path.basename(fixture_path))


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
        """
        Проверяет базовый сценарий выбора одной сущности.

        Что тестируется:
        1. Use case принимает карту {entity_id: selected} и меняет флаг у нужной сущности.
        2. Измененный документ сохраняется в репозитории.
        3. Публикуется событие on_document_modified для обновления UI.

        Почему это важно:
        Это центральный поток работы чекбоксов дерева DXF в интерфейсе.
        """
        self.active_repo.get_all.return_value = AppResult.success([self.document])
        self.active_repo.update.return_value = AppResult.success(self.document)

        result = self.use_case.execute({self.entity.id: False})

        self.assertTrue(result.is_success)
        self.assertFalse(self.entity.is_selected)
        self.assertEqual(self.active_repo.update.call_count, 1)
        self.assertEqual(len(self.events.on_document_modified.emitted), 1)

    def test_execute_selecting_layer_cascades_to_all_entities(self):
        """
        Проверяет каскадное поведение: когда выбирается слой, все его дочерние сущности
        должны получить то же состояние selected.

        Что тестируется:
        1. Передаем в use case ID слоя со значением False.
        2. Use case рекурсивно применяет выбор ко всем сущностям слоя.
        3. Репозиторий обновляется один раз для документа и событие модификации отправляется.

        Почему это важно:
        Без этого поведения кнопка "сохранить выбранное" может экспортировать лишние
        объекты, если пользователь снимал галку только на уровне слоя.
        """
        entity2 = DXFEntity(entity_type=DxfEntityType.CIRCLE, name="circle-1")
        first_layer = next(iter(self.document.layers.values()))
        first_layer.add_entities([entity2])

        self.active_repo.get_all.return_value = AppResult.success([self.document])
        self.active_repo.update.return_value = AppResult.success(self.document)

        result = self.use_case.execute({first_layer.id: False})

        self.assertTrue(result.is_success)
        self.assertFalse(self.entity.is_selected)
        self.assertFalse(entity2.is_selected)
        self.assertEqual(self.active_repo.update.call_count, 1)
        self.assertEqual(len(self.events.on_document_modified.emitted), 1)

    def test_execute_selecting_document_cascades_to_layers_and_entities(self):
        """
        Проверяет каскадное поведение на уровне документа.

        Что тестируется:
        1. При выборе документа use case должен изменить selected у самого документа,
           всех слоев и всех сущностей внутри этих слоев.
        2. Изменения должны сохраниться в репозитории и быть отражены в событии.

        Почему это важно:
        Это обеспечивает предсказуемую массовую операцию "выбрать/снять все" и
        корректные данные для последующих use case (импорт, экспорт, save selected).
        """
        second_layer = DXFLayer(
            document_id=self.document.id,
            name="L2",
            schema_name="layer_schema",
            table_name="l2",
        )
        second_entity = DXFEntity(entity_type=DxfEntityType.POINT, name="point-1")
        second_layer.add_entities([second_entity])
        self.document.add_layers([second_layer])

        self.active_repo.get_all.return_value = AppResult.success([self.document])
        self.active_repo.update.return_value = AppResult.success(self.document)

        result = self.use_case.execute({self.document.id: False})

        self.assertTrue(result.is_success)
        self.assertFalse(self.document.is_selected)
        self.assertTrue(all(not layer.is_selected for layer in self.document.layers.values()))
        self.assertTrue(
            all(
                not entity.is_selected
                for layer in self.document.layers.values()
                for entity in layer.entities.values()
            )
        )
        self.assertEqual(self.active_repo.update.call_count, 1)
        self.assertEqual(len(self.events.on_document_modified.emitted), 1)


class TestCloseDocumentUseCase(unittest.TestCase):
    def setUp(self):
        self.active_repo = MagicMock()
        self.writer = MagicMock()
        self.events = _DummyAppEvents()
        self.use_case = CloseDocumentUseCase(self.active_repo, self.writer, self.events)

    def test_execute_success_removes_document_and_emits_event(self):
        """
        Проверяет успешное закрытие документа.

        Что тестируется:
        1. Use case удаляет документ из активного репозитория по ID.
        2. Возвращается успешный результат.
        3. Публикуется событие on_document_closed с тем же ID.

        Почему это важно:
        Закрытие документа синхронизирует доменную модель и UI-дерево открытых файлов.
        """
        doc_id = uuid4()
        self.active_repo.remove.return_value = AppResult.success(Unit())

        result = self.use_case.execute(doc_id)

        self.assertTrue(result.is_success)
        self.active_repo.remove.assert_called_once_with(doc_id)
        self.assertEqual(self.events.on_document_closed.emitted, [doc_id])

    def test_execute_failure_returns_error_and_no_event(self):
        """
        Проверяет обработку ошибки при закрытии документа.

        Что тестируется:
        1. Если репозиторий вернул ошибку удаления, use case возвращает fail.
        2. Событие закрытия не отправляется, чтобы UI не потерял консистентность.

        Почему это важно:
        Нельзя сообщать об успешном закрытии, если документ фактически остался активным.
        """
        doc_id = uuid4()
        self.active_repo.remove.return_value = AppResult.fail("remove failed")

        result = self.use_case.execute(doc_id)

        self.assertTrue(result.is_fail)
        self.assertIn("remove failed", result.error)
        self.assertEqual(len(self.events.on_document_closed.emitted), 0)


class TestDataViewerUseCase(unittest.TestCase):
    def setUp(self):
        self.logger = _DummyLogger()
        self.use_case = DataViewerUseCase(self.logger)
        self.connection = ConnectionConfigDTO(
            db_type="postgis",
            name="local",
            host="localhost",
            port="5432",
            database="dxf",
            username="postgres",
            password="secret",
        )

    def test_get_schemas_returns_sorted_schemas(self):
        """
        Проверяет чтение списка схем и нормализацию порядка.

        Что тестируется:
        1. При успешном подключении use case запрашивает схемы из DBSession.
        2. Возвращаемый список отсортирован (важно для стабильного UI порядка).
        3. Сессия закрывается в finally-блоке.

        Почему это важно:
        Экспортная вкладка использует этот список напрямую, и нестабильный порядок
        ухудшает UX и может ломать повторяемость автотестов UI.
        """
        fake_session = MagicMock()
        fake_session.connect.return_value = AppResult.success(Unit())
        fake_session.get_schemas.return_value = AppResult.success(["z_schema", "a_schema"])

        with patch("src.application.use_cases.data_viewer_use_case.inject.instance", return_value=fake_session):
            result = self.use_case.get_schemas(self.connection)

        self.assertTrue(result.is_success)
        self.assertEqual(result.value, ["a_schema", "z_schema"])
        fake_session.close.assert_called_once()

    def test_get_filenames_returns_sorted_values_when_schema_exists(self):
        """
        Проверяет чтение списка DXF-файлов из конкретной схемы.

        Что тестируется:
        1. Use case проверяет существование схемы.
        2. Получает document repository и список документов.
        3. Возвращает отсортированный список имен файлов.

        Почему это важно:
        Это основной источник данных для дерева файлов на вкладке экспорта из БД.
        """
        fake_session = MagicMock()
        fake_session.connect.return_value = AppResult.success(Unit())
        fake_session.schema_exists.return_value = AppResult.success(True)

        docs_repo = MagicMock()
        docs_repo.get_all.return_value = AppResult.success([
            DXFDocument(filename="b_file.dxf", filepath=""),
            DXFDocument(filename="a_file.dxf", filepath=""),
        ])
        fake_session._get_document_repository.return_value = AppResult.success(docs_repo)

        with patch("src.application.use_cases.data_viewer_use_case.inject.instance", return_value=fake_session):
            result = self.use_case.get_filenames(self.connection, "file_schema")

        self.assertTrue(result.is_success)
        self.assertEqual(result.value, ["a_file.dxf", "b_file.dxf"])
        fake_session.close.assert_called_once()

    def test_get_filenames_returns_empty_when_schema_missing(self):
        """
        Проверяет ветку "схема не существует" без ошибки.

        Что тестируется:
        1. Если schema_exists вернул False, use case не идет в repository layer.
        2. Возвращается успешный пустой список как ожидаемое состояние.

        Почему это важно:
        Для новой/пустой БД это нормальный сценарий, который не должен пугать пользователя.
        """
        fake_session = MagicMock()
        fake_session.connect.return_value = AppResult.success(Unit())
        fake_session.schema_exists.return_value = AppResult.success(False)

        with patch("src.application.use_cases.data_viewer_use_case.inject.instance", return_value=fake_session):
            result = self.use_case.get_filenames(self.connection, "missing_schema")

        self.assertTrue(result.is_success)
        self.assertEqual(result.value, [])
        fake_session._get_document_repository.assert_not_called()
        fake_session.close.assert_called_once()


class TestSelectAreaUseCase(unittest.TestCase):
    def setUp(self):
        self.active_repo = MagicMock()
        self.area_selector = MagicMock()
        self.events = _DummyAppEvents()
        self.logger = _DummyLogger()
        self.use_case = SelectAreaUseCase(self.active_repo, self.area_selector, self.events, self.logger)

        self.document = DXFDocument(filename="doc_area.dxf", filepath="C:/tmp/doc_area.dxf")
        self.layer = DXFLayer(
            document_id=self.document.id,
            name="L1",
            schema_name="layer_schema",
            table_name="l1",
        )
        self.entity_a = DXFEntity(entity_type=DxfEntityType.LINE, name="line-a")
        self.entity_a.add_attributes({"handle": "AA11"})
        self.entity_b = DXFEntity(entity_type=DxfEntityType.CIRCLE, name="circle-b")
        self.entity_b.add_attributes({"handle": "BB22"})
        self.layer.add_entities([self.entity_a, self.entity_b])
        self.document.add_layers([self.layer])

        self.request = AreaSelectionRequestDTO(
            shape=ShapeType.RECTANGLE,
            selection_rule=SelectionRule.INTERSECT,
            selection_mode=SelectionMode.REPLACE,
            shape_args=(0, 0, 10, 10),
        )

    def test_execute_syncs_selection_by_handles_and_emits_modified(self):
        """
        Проверяет основной сценарий выбора по области с синхронизацией по handle.

        Что тестируется:
        1. Area selector возвращает список handle, попавших в область.
        2. Use case проставляет selected=True только соответствующим сущностям,
           остальные помечаются как selected=False.
        3. Родительские уровни (слой/документ) пересчитываются.
        4. Измененный документ сохраняется и отправляется событие модификации.

        Почему это важно:
        Эта логика влияет на фильтрацию, импорт и сохранение выбранных сущностей.
        """
        self.entity_a.set_selected(False)
        self.entity_b.set_selected(True)

        self.active_repo.get_by_filename.return_value = AppResult.success(self.document)
        self.active_repo.update.return_value = AppResult.success(self.document)
        self.area_selector.select_handles.return_value = AppResult.success(["aa11"])

        result = self.use_case.execute("doc_area.dxf", self.request)

        self.assertTrue(result.is_success)
        self.assertTrue(self.entity_a.is_selected)
        self.assertFalse(self.entity_b.is_selected)
        self.assertTrue(self.layer.is_selected)
        self.assertTrue(self.document.is_selected)
        self.assertEqual(len(self.events.on_document_modified.emitted), 1)

    def test_execute_clears_parent_selection_when_nothing_matched(self):
        """
        Проверяет пересчет родительских флагов, когда в область не попала ни одна сущность.

        Что тестируется:
        1. Для пустого списка handle все сущности становятся невыбранными.
        2. Слой и документ также становятся невыбранными через _refresh_parent_selection.

        Почему это важно:
        Иначе UI будет показывать "выбрано", хотя фактический набор сущностей пустой.
        """
        self.entity_a.set_selected(True)
        self.entity_b.set_selected(True)

        self.active_repo.get_by_filename.return_value = AppResult.success(self.document)
        self.active_repo.update.return_value = AppResult.success(self.document)
        self.area_selector.select_handles.return_value = AppResult.success([])

        result = self.use_case.execute("doc_area.dxf", self.request)

        self.assertTrue(result.is_success)
        self.assertFalse(self.entity_a.is_selected)
        self.assertFalse(self.entity_b.is_selected)
        self.assertFalse(self.layer.is_selected)
        self.assertFalse(self.document.is_selected)


class TestImportUseCase(unittest.TestCase):
    def setUp(self):
        self.active_repo = MagicMock()
        self.logger = _DummyLogger()
        self.dxf_reader = MagicMock()
        self.dxf_writer = MagicMock()
        self.dxf_reader.save_svg_preview.return_value = AppResult.success("preview.svg")
        self.dxf_writer.save_selected_by_handles.return_value = AppResult.success(0)
        self.use_case = ImportUseCase(self.active_repo, self.dxf_reader, self.dxf_writer, self.logger)

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
        """
        Проверяет отказ импорта без параметров подключения.

        Что тестируется:
        1. Execute возвращает fail при connection=None.
        2. Отчет содержит стартовый заголовок процесса импорта.

        Почему это важно:
        Сообщение об ошибке и отчет должны быть полезны для пользователя и логов.
        """
        result, report = self.use_case.execute(None, [])

        self.assertTrue(result.is_fail)
        self.assertIn("No connection", result.error)
        self.assertIn("Starting DXF import process", report)

    def test_execute_fails_when_document_not_found(self):
        """
        Проверяет сценарий, когда выбранный документ отсутствует в active repository.

        Что тестируется:
        1. Репозиторий возвращает fail для get_by_filename.
        2. Execute завершает импорт с fail и отражает причину в отчете.

        Почему это важно:
        Это частый пользовательский случай при рассинхронизации UI и активных документов.
        """
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
        """
        Проверяет успешную ветку импорта в режиме "только слои".

        Что тестируется:
        1. При валидных параметрах и доступной схеме импорт завершается успешно.
        2. Сессия коммитится и закрывается.
        3. Отчет содержит success-footer.

        Почему это важно:
        Это базовый и безопасный путь импорта для предварительной подготовки структуры БД.
        """
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

    def test_execute_uses_only_selected_entities_when_selection_exists(self):
        """
        Проверяет, что при наличии выбранных сущностей импорт пишет в writer только их.

        Что тестируется:
        1. В документе есть выбранная и невыбранная сущности.
        2. ImportUseCase вызывает writer для подготовки временного DXF.
        3. В writer передается только handle выбранной сущности.

        Почему это важно:
        Это регрессионная проверка на баг, когда в импорт попадал весь файл вместо выбора.
        """
        doc = DXFDocument(filename="subset.dxf", filepath="")
        layer = DXFLayer.create(
            document_id=doc.id,
            name="Layer1",
            schema_name="public",
            table_name="Layer1",
        )

        selected_entity = DXFEntity.create(
            entity_type=DxfEntityType.LINE,
            name="selected",
            selected=True,
        )
        selected_entity.add_attributes({"handle": "ABCD12"})

        other_entity = DXFEntity.create(
            entity_type=DxfEntityType.LINE,
            name="other",
            selected=False,
        )
        other_entity.add_attributes({"handle": "FFFF00"})

        layer.add_entities([selected_entity, other_entity])
        doc.add_layers([layer])
        doc.add_content(DXFContent(document_id=doc.id, content=b"0\nEOF\n"))

        config = ImportConfigDTO(
            filename="subset.dxf",
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

        self.assertTrue(result.is_success, msg=report)
        self.dxf_writer.save_selected_by_handles.assert_called_once()
        call_kwargs = self.dxf_writer.save_selected_by_handles.call_args.kwargs
        self.assertEqual(call_kwargs["selected_handles"], {"ABCD12"})

    def test_execute_fails_when_layer_schema_not_found(self):
        """
        Проверяет обработку отсутствующей schema для слоев.

        Что тестируется:
        1. schema_exists возвращает False для layer-schema.
        2. ImportUseCase возвращает fail.
        3. В отчете присутствует явное сообщение о несуществующей схеме.

        Почему это важно:
        Пользователь должен сразу понимать, что нужна подготовка схем перед импортом.
        """
        doc = DXFDocument(filename="ok.dxf", filepath="C:/tmp/ok.dxf")
        doc.add_content(DXFContent(document_id=doc.id, content=b"0\nEOF\n"))
        self.active_repo.get_by_filename.return_value = AppResult.success(doc)

        config = ImportConfigDTO(
            filename="ok.dxf",
            import_mode=ImportMode.ADD_OBJECTS,
            layer_schema="missing_layer_schema",
            file_schema="file_schema",
            import_layers_only=True,
        )

        fake_session = MagicMock()
        fake_session.connect.return_value = AppResult.success(Unit())
        fake_session.schema_exists.side_effect = [AppResult.success(False)]

        with patch("src.application.use_cases.import_use_case.inject.instance", return_value=fake_session):
            result, report = self.use_case.execute(self.connection, [config])

        self.assertTrue(result.is_fail)
        self.assertIn("does not exist", report)


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
        """
        Проверяет валидацию списка конфигов на входе ExportUseCase.

        Что тестируется:
        1. При пустом configs экспорт не стартует и возвращает fail.
        2. Отчет содержит стартовую запись процесса.

        Почему это важно:
        Исключает ложный "успех" при пустом пользовательском вводе.
        """
        result, report = self.use_case.execute(self.connection, [])

        self.assertTrue(result.is_fail)
        self.assertIn("No configs", result.error)
        self.assertIn("Starting DXF export process", report)

    def test_execute_writes_output_file(self):
        """
        Проверяет успешный экспорт контента из БД в файл DXF на диске.

        Что тестируется:
        1. Use case получает документ и бинарный контент через репозитории.
        2. Контент записывается в output_path.
        3. Возвращается success и отчет содержит финальный маркер.

        Почему это важно:
        Это основной рабочий сценарий экспорта PostGIS -> DXF.
        """
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

    def test_execute_fails_when_document_not_found(self):
        """
        Проверяет отказ экспорта при отсутствии документа в БД.

        Что тестируется:
        1. Document repository возвращает fail для указанного filename.
        2. ExportUseCase возвращает fail и сохраняет причину в отчете.

        Почему это важно:
        Позволяет корректно обрабатывать рассинхронизацию метаданных и контента в БД.
        """
        doc_repo = MagicMock()
        doc_repo.get_by_filename.return_value = AppResult.fail("not found")

        content_repo = MagicMock()

        fake_session = MagicMock()
        fake_session.connect.return_value = AppResult.success(Unit())
        fake_session.schema_exists.return_value = AppResult.success(True)
        fake_session._get_document_repository.return_value = AppResult.success(doc_repo)
        fake_session._get_content_repository.return_value = AppResult.success(content_repo)

        config = ExportConfigDTO(
            filename="missing.dxf",
            export_mode=ExportMode.FILE,
            output_path=os.path.join(tempfile.gettempdir(), "missing_export.dxf"),
            file_schema="file_schema",
        )

        with patch("src.application.use_cases.export_use_case.inject.instance", return_value=fake_session):
            result, report = self.use_case.execute(self.connection, [config])

        self.assertTrue(result.is_fail)
        self.assertIn("not found", report)


class TestSaveSelectedToFileUseCase(unittest.TestCase):
    def setUp(self):
        self.logger = _DummyLogger()
        self.events = _DummyAppEvents()
        self.active_repo = ActiveDocumentRepository()
        self.reader = DXFReader()
        self.writer = DXFWriter()
        self.open_use_case = OpenDocumentUseCase(self.active_repo, self.reader, self.events, self.logger)
        self.select_use_case = SelectEntityUseCase(self.active_repo, self.events, self.logger)
        self.save_use_case = SaveSelectedToFileUseCase(self.active_repo, self.writer, self.logger)

    def test_save_only_selected_entities_with_real_file(self):
        """
        Проверяет экспорт только выбранных сущностей в новый DXF на реальном файле.

        Что тестируется:
        1. Из реального fixture-файла выбирается одна сущность с валидным handle.
        2. Через SelectEntityUseCase все остальные сущности снимаются.
        3. SaveSelectedToFileUseCase создает новый файл.
        4. В экспортированном файле присутствует ровно одна сущность с ожидаемым handle.

        Почему это важно:
        Это ключевая пользовательская функция кнопки сохранения выбранных объектов.
        """
        open_result = self.open_use_case.execute_single(EXAMPLE_3)
        self.assertTrue(open_result.is_success, msg=open_result.error if open_result.is_fail else "")

        doc = open_result.value
        all_entities = [
            entity
            for layer in doc.layers
            for entity in layer.entities
        ]
        self.assertGreater(len(all_entities), 0)

        selected_entity = next(
            (entity for entity in all_entities if str(entity.attributes.get("handle", "")).strip()),
            None,
        )
        if selected_entity is None:
            self.skipTest("No entities with non-empty handle in fixture file")

        selection_map = {entity.id: entity.id == selected_entity.id for entity in all_entities}
        select_result = self.select_use_case.execute(selection_map)
        self.assertTrue(select_result.is_success, msg=select_result.error if select_result.is_fail else "")

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = os.path.join(tmp_dir, "selected_only.dxf")
            save_result, report = self.save_use_case.execute(doc.filename, out_path)

            self.assertTrue(save_result.is_success, msg=save_result.error if save_result.is_fail else report)
            self.assertTrue(os.path.exists(out_path))

            exported_doc_result = self.reader.open(out_path)
            self.assertTrue(exported_doc_result.is_success, msg=exported_doc_result.error if exported_doc_result.is_fail else "")
            exported_doc = exported_doc_result.value
            exported_handles = {
                str(entity.attributes.get("handle", "")).strip().upper()
                for layer in exported_doc.layers.values()
                for entity in layer.entities.values()
                if str(entity.attributes.get("handle", "")).strip()
            }
            selected_handle = str(selected_entity.attributes.get("handle", "")).strip().upper()

            self.assertIn(selected_handle, exported_handles)
            self.assertEqual(len(exported_handles), 1)

    def test_save_fails_when_nothing_selected(self):
        """
        Проверяет защитный сценарий сохранения при пустом выборе.

        Что тестируется:
        1. Все сущности в документе принудительно снимаются через SelectEntityUseCase.
        2. SaveSelectedToFileUseCase возвращает fail.
        3. Ошибка и отчет явно сообщают об отсутствии выбранных сущностей.

        Почему это важно:
        Исключает создание некорректных файлов и дает пользователю понятную причину отказа.
        """
        open_result = self.open_use_case.execute_single(EXAMPLE_2)
        self.assertTrue(open_result.is_success, msg=open_result.error if open_result.is_fail else "")

        doc = open_result.value
        all_entities = [
            entity
            for layer in doc.layers
            for entity in layer.entities
        ]
        self.assertGreater(len(all_entities), 0)

        select_result = self.select_use_case.execute({entity.id: False for entity in all_entities})
        self.assertTrue(select_result.is_success, msg=select_result.error if select_result.is_fail else "")

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = os.path.join(tmp_dir, "nothing_selected.dxf")
            save_result, report = self.save_use_case.execute(doc.filename, out_path)

            self.assertTrue(save_result.is_fail)
            self.assertIn("No selected entities", save_result.error)
            self.assertIn("No selected entities", report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
