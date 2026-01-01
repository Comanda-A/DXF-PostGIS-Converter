# -*- coding: utf-8 -*-
"""
Unit Tests для рефакторированных сервисов.

Запуск тестов:
    python -m pytest tests/test_services.py -v
    
Или через QGIS Python Console:
    import unittest
    from tests.test_services import *
    unittest.main(module='tests.test_services', exit=False)
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass


class TestSettingsService(unittest.TestCase):
    """Тесты для SettingsService."""
    
    def setUp(self):
        """Подготовка к тестам."""
        # Патчим QgsSettings чтобы не зависеть от QGIS
        self.settings_patcher = patch('src.application.settings_service.QgsSettings')
        self.mock_qgs_settings = self.settings_patcher.start()
        self.mock_settings_instance = MagicMock()
        self.mock_qgs_settings.return_value = self.mock_settings_instance
        
        # Сбрасываем singleton
        from src.application.settings_service import SettingsService
        SettingsService._instance = None
        self.service = SettingsService.instance()
    
    def tearDown(self):
        """Очистка после тестов."""
        self.settings_patcher.stop()
        from src.application.settings_service import SettingsService
        SettingsService._instance = None
    
    def test_singleton_pattern(self):
        """SettingsService должен быть singleton."""
        from src.application.settings_service import SettingsService
        service1 = SettingsService.instance()
        service2 = SettingsService.instance()
        self.assertIs(service1, service2)
    
    def test_set_and_get_language(self):
        """Должен сохранять и получать язык."""
        self.mock_settings_instance.value.return_value = "ru"
        
        lang = self.service.get_language()
        self.assertEqual(lang, "ru")
        
        self.service.set_language("en")
        self.mock_settings_instance.setValue.assert_called()
    
    def test_is_logging_enabled(self):
        """Должен возвращать статус логирования."""
        self.mock_settings_instance.value.return_value = True
        self.assertTrue(self.service.is_logging_enabled())
        
        self.mock_settings_instance.value.return_value = False
        self.assertFalse(self.service.is_logging_enabled())


class TestConnectionSettings(unittest.TestCase):
    """Тесты для ConnectionSettings dataclass."""
    
    def test_is_configured(self):
        """Должен проверять настроенность подключения."""
        from src.application.settings_service import ConnectionSettings
        
        # Ненастроенное подключение
        conn_default = ConnectionSettings()
        self.assertFalse(conn_default.is_configured)
        
        # Настроенное подключение
        conn = ConnectionSettings(
            host="localhost",
            port="5432",
            database="testdb",
            username="user",
            password="pass"
        )
        self.assertTrue(conn.is_configured)
    
    def test_display_name(self):
        """Должен формировать отображаемое имя."""
        from src.application.settings_service import ConnectionSettings
        
        conn = ConnectionSettings(
            host="localhost",
            port="5432",
            database="testdb",
            username="user",
            password="pass"
        )
        
        display = conn.display_name
        
        self.assertIn("localhost", display)
        self.assertIn("5432", display)
        self.assertIn("testdb", display)


class TestValidationResult(unittest.TestCase):
    """Тесты для ValidationResult."""
    
    def test_valid_result(self):
        """Валидный результат без ошибок."""
        from src.domain.models.result import ValidationResult
        
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
    
    def test_invalid_result_with_errors(self):
        """Невалидный результат с ошибками."""
        from src.domain.models.result import ValidationResult
        
        result = ValidationResult(
            is_valid=False, 
            errors=["Error 1", "Error 2"], 
            warnings=[]
        )
        
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 2)
    
    def test_result_with_warnings(self):
        """Результат с предупреждениями."""
        from src.domain.models.result import ValidationResult
        
        result = ValidationResult(
            is_valid=True, 
            errors=[], 
            warnings=["Warning 1"]
        )
        
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.warnings), 1)


class TestImportConfig(unittest.TestCase):
    """Тесты для ImportConfig."""
    
    def test_create_import_config(self):
        """Создание конфигурации импорта."""
        from src.domain.models.config import ImportConfig
        from src.application.settings_service import ConnectionSettings
        
        conn = ConnectionSettings(
            host="localhost",
            port="5432",
            database="testdb",
            username="user",
            password="pass"
        )
        
        config = ImportConfig(
            connection=conn,
            layer_schema="public",
            file_schema="dxf_files"
        )
        
        self.assertEqual(config.layer_schema, "public")
        self.assertEqual(config.file_schema, "dxf_files")
        self.assertIsNotNone(config.connection)


class TestExportConfig(unittest.TestCase):
    """Тесты для ExportConfig."""
    
    def test_create_export_config(self):
        """Создание конфигурации экспорта."""
        from src.domain.models.config import ExportConfig
        from src.application.settings_service import ConnectionSettings
        
        conn = ConnectionSettings(
            host="localhost",
            port="5432",
            database="testdb",
            username="user",
            password="pass"
        )
        
        config = ExportConfig(
            connection=conn,
            file_id=1,
            destination="file",
            output_path="/path/to/output.dxf"
        )
        
        self.assertEqual(config.file_id, 1)
        self.assertEqual(config.destination, "file")


class TestImportService(unittest.TestCase):
    """Тесты для ImportService."""
    
    def setUp(self):
        """Подготовка mock-объектов."""
        self.mock_connection = Mock()
        self.mock_repository = Mock()
        
        from src.application.import_service import ImportService
        self.service = ImportService(
            connection=self.mock_connection,
            repository=self.mock_repository
        )
    
    def test_validate_config_unconfigured_connection(self):
        """Валидация должна выявлять ненастроенное подключение."""
        from src.domain.models.config import ImportConfig
        from src.application.settings_service import ConnectionSettings
        
        # Ненастроенное подключение (значения по умолчанию)
        conn = ConnectionSettings()  # host='none', database='none'
        
        config = ImportConfig(
            connection=conn,
            layer_schema="public"
        )
        
        result = self.service.validate_config(config)
        
        self.assertFalse(result.is_valid)
        self.assertTrue(len(result.errors) > 0)
    
    def test_validate_config_empty_layer_schema(self):
        """Валидация должна выявлять отсутствие схемы слоёв."""
        from src.domain.models.config import ImportConfig
        from src.application.settings_service import ConnectionSettings
        
        conn = ConnectionSettings(
            host="localhost",
            port="5432",
            database="testdb",
            username="user",
            password="pass"
        )
        
        config = ImportConfig(
            connection=conn,
            layer_schema=""  # Пустая схема
        )
        
        result = self.service.validate_config(config)
        
        self.assertFalse(result.is_valid)
        self.assertTrue(any("схема" in e.lower() or "слой" in e.lower() for e in result.errors))
    
    def test_validate_config_valid(self):
        """Валидация корректной конфигурации."""
        from src.domain.models.config import ImportConfig
        from src.application.settings_service import ConnectionSettings
        
        conn = ConnectionSettings(
            host="localhost",
            port="5432",
            database="testdb",
            username="user",
            password="pass"
        )
        
        config = ImportConfig(
            connection=conn,
            layer_schema="public",
            file_schema="dxf_files"
        )
        
        result = self.service.validate_config(config)
        
        self.assertTrue(result.is_valid)


class TestExportService(unittest.TestCase):
    """Тесты для ExportService."""
    
    def setUp(self):
        """Подготовка mock-объектов."""
        self.mock_connection = Mock()
        self.mock_repository = Mock()
        
        from src.application.export_service import ExportService
        self.service = ExportService(
            db_connection=self.mock_connection,
            repository=self.mock_repository
        )
    
    def test_validate_export_config_empty_host(self):
        """Валидация должна выявлять пустой хост."""
        from src.domain.models.config import ExportConfig
        from src.application.settings_service import ConnectionSettings
        
        # Подключение с пустым хостом
        conn = ConnectionSettings(
            host="",
            port="5432",
            database="testdb",
            username="user",
            password="pass"
        )
        
        config = ExportConfig(
            connection=conn,
            file_id=1
        )
        
        result = self.service.validate_export_config(config)
        
        self.assertFalse(result.is_valid)
        self.assertTrue(any("хост" in e.lower() for e in result.errors))
    
    def test_validate_export_config_invalid_file_id(self):
        """Валидация должна выявлять невалидный file_id."""
        from src.domain.models.config import ExportConfig
        from src.application.settings_service import ConnectionSettings
        
        conn = ConnectionSettings(
            host="localhost",
            port="5432",
            database="testdb",
            username="user",
            password="pass"
        )
        
        config = ExportConfig(
            connection=conn,
            file_id=0  # Невалидный ID
        )
        
        result = self.service.validate_export_config(config)
        
        self.assertFalse(result.is_valid)
        self.assertTrue(any("id" in e.lower() for e in result.errors))
    
    def test_validate_export_config_valid(self):
        """Валидация корректной конфигурации экспорта."""
        from src.domain.models.config import ExportConfig
        from src.application.settings_service import ConnectionSettings
        
        conn = ConnectionSettings(
            host="localhost",
            port="5432",
            database="testdb",
            username="user",
            password="pass"
        )
        
        config = ExportConfig(
            connection=conn,
            file_id=1,
            destination="qgis"
        )
        
        result = self.service.validate_export_config(config)
        
        self.assertTrue(result.is_valid)


class TestDependencyContainer(unittest.TestCase):
    """Тесты для DependencyContainer."""
    
    def setUp(self):
        """Сброс singleton перед каждым тестом."""
        from src.container import DependencyContainer
        DependencyContainer._instance = None
    
    def tearDown(self):
        """Сброс singleton после каждого теста."""
        from src.container import DependencyContainer
        DependencyContainer._instance = None
    
    def test_singleton_pattern(self):
        """Container должен быть singleton."""
        from src.container import DependencyContainer
        
        container1 = DependencyContainer.instance()
        container2 = DependencyContainer.instance()
        
        self.assertIs(container1, container2)
    
    def test_lazy_initialization(self):
        """Сервисы должны создаваться лениво."""
        from src.container import DependencyContainer
        
        container = DependencyContainer.instance()
        
        # Приватные поля должны быть None до доступа
        self.assertIsNone(container._settings_service)
        self.assertIsNone(container._import_service)
        self.assertIsNone(container._export_service)
    
    @patch('src.application.settings_service.QgsSettings')
    def test_settings_service_access(self, mock_qgs):
        """Доступ к settings_service должен создавать экземпляр."""
        from src.container import DependencyContainer
        
        container = DependencyContainer.instance()
        service = container.settings_service
        
        self.assertIsNotNone(service)
        # Повторный доступ должен вернуть тот же экземпляр
        self.assertIs(service, container.settings_service)


class TestEntitySelector(unittest.TestCase):
    """Тесты для EntitySelector."""
    
    def test_get_selection_count_nonexistent(self):
        """Получение количества выделенных сущностей для незарегистрированного файла."""
        from src.domain.dxf.entity_selector import EntitySelector
        
        selector = EntitySelector()
        
        # Для незарегистрированного файла должен вернуть 0
        count = selector.get_selection_count("nonexistent.dxf")
        self.assertEqual(count, 0)
    
    def test_clear_selection(self):
        """Очистка выделения."""
        from src.domain.dxf.entity_selector import EntitySelector
        
        selector = EntitySelector()
        
        # Для незарегистрированного файла очистка не должна вызывать ошибок
        selector.clear_selection("nonexistent.dxf")
        
        selection = selector.get_selection("nonexistent.dxf")
        self.assertEqual(len(selection), 0)
    
    def test_get_selection_empty(self):
        """Получение пустого выделения."""
        from src.domain.dxf.entity_selector import EntitySelector
        
        selector = EntitySelector()
        selection = selector.get_selection("test.dxf")
        
        self.assertIsInstance(selection, list)
        self.assertEqual(len(selection), 0)


class TestDxfDocument(unittest.TestCase):
    """Тесты для DxfDocument."""
    
    @patch('src.domain.dxf.dxf_document.ezdxf')
    def test_load_document(self, mock_ezdxf):
        """Загрузка документа."""
        from src.domain.dxf.dxf_document import DxfDocument
        
        # Настраиваем mock
        mock_doc = Mock()
        mock_msp = Mock()
        mock_doc.modelspace.return_value = mock_msp
        mock_ezdxf.readfile.return_value = mock_doc
        
        doc = DxfDocument()
        result = doc.load("/path/to/test.dxf")
        
        self.assertTrue(result)
        mock_ezdxf.readfile.assert_called_once()
    
    def test_document_not_loaded(self):
        """Документ без загрузки."""
        from src.domain.dxf.dxf_document import DxfDocument
        
        doc = DxfDocument()
        
        # Без загрузки должен вернуть пустые данные
        self.assertFalse(doc.is_loaded)
        self.assertEqual(doc.get_all_entities(), [])


# ========== Test Runner ==========

def run_tests():
    """Запуск всех тестов."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Добавляем все тестовые классы
    suite.addTests(loader.loadTestsFromTestCase(TestSettingsService))
    suite.addTests(loader.loadTestsFromTestCase(TestConnectionSettings))
    suite.addTests(loader.loadTestsFromTestCase(TestValidationResult))
    suite.addTests(loader.loadTestsFromTestCase(TestImportConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestExportConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestImportService))
    suite.addTests(loader.loadTestsFromTestCase(TestExportService))
    suite.addTests(loader.loadTestsFromTestCase(TestDependencyContainer))
    suite.addTests(loader.loadTestsFromTestCase(TestEntitySelector))
    suite.addTests(loader.loadTestsFromTestCase(TestDxfDocument))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == '__main__':
    run_tests()
