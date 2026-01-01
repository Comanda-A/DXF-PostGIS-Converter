# -*- coding: utf-8 -*-
"""
Интеграционные тесты с реальной PostgreSQL/PostGIS БД.

Требования:
- Доступная PostgreSQL БД с PostGIS
- Переменные окружения для подключения (или конфиг ниже)

Запуск:
    # Установить переменные окружения:
    set TEST_DB_HOST=localhost
    set TEST_DB_PORT=5432
    set TEST_DB_NAME=test_dxf_converter
    set TEST_DB_USER=postgres
    set TEST_DB_PASSWORD=password
    
    # Запустить тесты:
    python -m pytest tests/test_integration.py -v
    
    # Или через QGIS Python Console
"""

import os
import sys
import unittest
import tempfile
from pathlib import Path

# Добавляем путь к плагину
plugin_path = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_path))

# Mock QGIS если не в QGIS среде
try:
    from qgis.core import QgsSettings
    IN_QGIS = True
except ImportError:
    from unittest.mock import MagicMock
    sys.modules['qgis'] = MagicMock()
    sys.modules['qgis.core'] = MagicMock()
    sys.modules['qgis.PyQt'] = MagicMock()
    sys.modules['qgis.PyQt.QtCore'] = MagicMock()
    sys.modules['qgis.PyQt.QtWidgets'] = MagicMock()
    sys.modules['qgis.PyQt.QtGui'] = MagicMock()
    IN_QGIS = False


def get_test_db_config():
    """Получить конфигурацию тестовой БД из переменных окружения."""
    from src.application.settings_service import ConnectionSettings
    
    return ConnectionSettings(
        host=os.environ.get('TEST_DB_HOST', 'localhost'),
        port=os.environ.get('TEST_DB_PORT', '5432'),
        database=os.environ.get('TEST_DB_NAME', 'test_dxf_converter'),
        username=os.environ.get('TEST_DB_USER', 'postgres'),
        password=os.environ.get('TEST_DB_PASSWORD', 'password')
    )


def skip_if_no_db():
    """Декоратор для пропуска тестов если БД недоступна."""
    try:
        from src.infrastructure.database import DatabaseConnection
        conn = DatabaseConnection()
        config = get_test_db_config()
        session = conn.connect(config)
        if session:
            session.close()
            return lambda f: f  # Не пропускать
        return unittest.skip("Database not available")
    except Exception as e:
        return unittest.skip(f"Database not available: {e}")


class TestDatabaseConnectionIntegration(unittest.TestCase):
    """Интеграционные тесты DatabaseConnection."""
    
    @classmethod
    def setUpClass(cls):
        """Проверка доступности БД."""
        from src.infrastructure.database import DatabaseConnection
        cls.db_connection = DatabaseConnection()
        cls.config = get_test_db_config()
        
        # Проверяем подключение
        session = cls.db_connection.connect(cls.config)
        if not session:
            raise unittest.SkipTest("Cannot connect to test database")
        session.close()
    
    def test_connect_and_disconnect(self):
        """Тест подключения и отключения."""
        session = self.db_connection.connect(self.config)
        
        self.assertIsNotNone(session)
        
        # Проверяем что сессия рабочая
        result = session.execute("SELECT 1").scalar()
        self.assertEqual(result, 1)
        
        session.close()
    
    def test_test_connection(self):
        """Тест метода test_connection."""
        success, message = self.db_connection.test_connection(self.config)
        
        self.assertTrue(success)
        self.assertIn("успешно", message.lower())
    
    def test_ensure_postgis_extension(self):
        """Тест создания PostGIS расширения."""
        session = self.db_connection.connect(self.config)
        
        try:
            self.db_connection.ensure_postgis_extension(session)
            
            # Проверяем что PostGIS доступен
            result = session.execute(
                "SELECT PostGIS_Version()"
            ).scalar()
            
            self.assertIsNotNone(result)
            
        finally:
            session.close()


class TestDxfRepositoryIntegration(unittest.TestCase):
    """Интеграционные тесты DxfRepository."""
    
    TEST_SCHEMA = 'test_dxf_integration'
    
    @classmethod
    def setUpClass(cls):
        """Настройка тестовой схемы."""
        from src.infrastructure.database import DatabaseConnection, DxfRepository
        
        cls.db_connection = DatabaseConnection()
        cls.config = get_test_db_config()
        cls.repository = DxfRepository(cls.db_connection)
        
        # Проверяем подключение
        session = cls.db_connection.connect(cls.config)
        if not session:
            raise unittest.SkipTest("Cannot connect to test database")
        
        try:
            # Создаём тестовую схему
            session.execute(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE")
            session.execute(f"CREATE SCHEMA {cls.TEST_SCHEMA}")
            session.commit()
        finally:
            session.close()
    
    @classmethod
    def tearDownClass(cls):
        """Удаление тестовой схемы."""
        session = cls.db_connection.connect(cls.config)
        if session:
            try:
                session.execute(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE")
                session.commit()
            finally:
                session.close()
    
    def test_create_and_get_file(self):
        """Тест создания и получения файла."""
        session = self.db_connection.connect(self.config)
        
        try:
            # Создаём файл
            test_content = b"TEST DXF CONTENT"
            file_id = self.repository.create_file(
                session,
                filename="test_file.dxf",
                file_content=test_content,
                schema_name=self.TEST_SCHEMA
            )
            
            self.assertIsNotNone(file_id)
            self.assertGreater(file_id, 0)
            
            # Получаем файл
            file_record = self.repository.get_file_by_id(session, file_id)
            
            self.assertIsNotNone(file_record)
            self.assertEqual(file_record.filename, "test_file.dxf")
            self.assertEqual(file_record.file_content, test_content)
            
        finally:
            session.close()
    
    def test_get_all_files(self):
        """Тест получения списка файлов."""
        session = self.db_connection.connect(self.config)
        
        try:
            # Создаём несколько файлов
            for i in range(3):
                self.repository.create_file(
                    session,
                    filename=f"batch_test_{i}.dxf",
                    file_content=f"CONTENT {i}".encode(),
                    schema_name=self.TEST_SCHEMA
                )
            
            # Получаем список
            files = self.repository.get_all_files(session, schema_name=self.TEST_SCHEMA)
            
            self.assertGreaterEqual(len(files), 3)
            
        finally:
            session.close()
    
    def test_delete_file(self):
        """Тест удаления файла."""
        session = self.db_connection.connect(self.config)
        
        try:
            # Создаём файл
            file_id = self.repository.create_file(
                session,
                filename="to_delete.dxf",
                file_content=b"DELETE ME",
                schema_name=self.TEST_SCHEMA
            )
            
            # Удаляем
            self.repository.delete_file(session, file_id)
            
            # Проверяем что удалён
            file_record = self.repository.get_file_by_id(session, file_id)
            self.assertIsNone(file_record)
            
        finally:
            session.close()
    
    def test_create_layer_table(self):
        """Тест создания таблицы слоя."""
        session = self.db_connection.connect(self.config)
        
        try:
            layer_name = "test_layer"
            
            self.repository.create_layer_table(
                session, 
                layer_name, 
                self.TEST_SCHEMA
            )
            
            # Проверяем что таблица создана
            result = session.execute(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = '{self.TEST_SCHEMA}'
                    AND table_name = '{layer_name}'
                )
            """).scalar()
            
            self.assertTrue(result)
            
        finally:
            session.close()


class TestImportServiceIntegration(unittest.TestCase):
    """Интеграционные тесты ImportService."""
    
    TEST_SCHEMA = 'test_import_integration'
    
    @classmethod
    def setUpClass(cls):
        """Настройка."""
        from src.infrastructure.database import DatabaseConnection, DxfRepository
        from src.application.import_service import ImportService
        
        cls.db_connection = DatabaseConnection()
        cls.config = get_test_db_config()
        cls.repository = DxfRepository(cls.db_connection)
        cls.import_service = ImportService(
            connection=cls.db_connection,
            repository=cls.repository
        )
        
        session = cls.db_connection.connect(cls.config)
        if not session:
            raise unittest.SkipTest("Cannot connect to test database")
        
        try:
            session.execute(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE")
            session.execute(f"CREATE SCHEMA {cls.TEST_SCHEMA}")
            session.commit()
        finally:
            session.close()
    
    @classmethod
    def tearDownClass(cls):
        """Очистка."""
        session = cls.db_connection.connect(cls.config)
        if session:
            try:
                session.execute(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE")
                session.commit()
            finally:
                session.close()
    
    def test_validate_config_valid(self):
        """Тест валидации корректной конфигурации."""
        from src.domain.models.config import ImportConfig
        
        config = ImportConfig(
            connection=self.config,
            layer_schema=self.TEST_SCHEMA,
            file_schema=self.TEST_SCHEMA
        )
        
        result = self.import_service.validate_config(config)
        
        self.assertTrue(result.is_valid)
    
    def test_get_available_schemas(self):
        """Тест получения списка схем."""
        from src.domain.models.config import ImportConfig
        
        config = ImportConfig(
            connection=self.config,
            layer_schema=self.TEST_SCHEMA,
            file_schema=self.TEST_SCHEMA
        )
        
        schemas = self.import_service.get_available_schemas(config)
        
        self.assertIsInstance(schemas, list)
        self.assertIn(self.TEST_SCHEMA, schemas)


class TestExportServiceIntegration(unittest.TestCase):
    """Интеграционные тесты ExportService."""
    
    TEST_SCHEMA = 'test_export_integration'
    
    @classmethod
    def setUpClass(cls):
        """Настройка."""
        from src.infrastructure.database import DatabaseConnection, DxfRepository
        from src.application.export_service import ExportService
        
        cls.db_connection = DatabaseConnection()
        cls.config = get_test_db_config()
        cls.repository = DxfRepository(cls.db_connection)
        cls.export_service = ExportService(
            db_connection=cls.db_connection,
            repository=cls.repository
        )
        
        session = cls.db_connection.connect(cls.config)
        if not session:
            raise unittest.SkipTest("Cannot connect to test database")
        
        try:
            session.execute(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE")
            session.execute(f"CREATE SCHEMA {cls.TEST_SCHEMA}")
            session.commit()
            
            # Создаём тестовый файл
            cls.test_file_id = cls.repository.create_file(
                session,
                filename="export_test.dxf",
                file_content=b"0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n",
                schema_name=cls.TEST_SCHEMA
            )
            
        finally:
            session.close()
    
    @classmethod
    def tearDownClass(cls):
        """Очистка."""
        session = cls.db_connection.connect(cls.config)
        if session:
            try:
                session.execute(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE")
                session.commit()
            finally:
                session.close()
    
    def test_validate_export_config_valid(self):
        """Тест валидации корректной конфигурации экспорта."""
        from src.domain.models.config import ExportConfig
        
        config = ExportConfig(
            connection=self.config,
            file_id=self.test_file_id,
            destination="qgis"
        )
        
        result = self.export_service.validate_export_config(config)
        
        self.assertTrue(result.is_valid)
    
    def test_export_to_temp_file(self):
        """Тест экспорта во временный файл."""
        from src.domain.models.config import ExportConfig
        
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as f:
            temp_path = f.name
        
        try:
            config = ExportConfig(
                connection=self.config,
                file_id=self.test_file_id,
                destination="file",
                output_path=temp_path
            )
            
            result = self.export_service.export_from_database(config)
            
            self.assertTrue(result.success)
            self.assertTrue(os.path.exists(temp_path))
            
            # Проверяем содержимое
            with open(temp_path, 'rb') as f:
                content = f.read()
            self.assertIn(b"SECTION", content)
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestFullImportExportCycle(unittest.TestCase):
    """Полный цикл импорт-экспорт."""
    
    TEST_SCHEMA = 'test_full_cycle'
    
    @classmethod
    def setUpClass(cls):
        """Настройка."""
        from src.infrastructure.database import DatabaseConnection, DxfRepository
        from src.application.import_service import ImportService
        from src.application.export_service import ExportService
        
        cls.db_connection = DatabaseConnection()
        cls.config = get_test_db_config()
        cls.repository = DxfRepository(cls.db_connection)
        cls.import_service = ImportService(
            connection=cls.db_connection,
            repository=cls.repository
        )
        cls.export_service = ExportService(
            db_connection=cls.db_connection,
            repository=cls.repository
        )
        
        session = cls.db_connection.connect(cls.config)
        if not session:
            raise unittest.SkipTest("Cannot connect to test database")
        
        try:
            session.execute(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE")
            session.execute(f"CREATE SCHEMA {cls.TEST_SCHEMA}")
            session.commit()
        finally:
            session.close()
    
    @classmethod
    def tearDownClass(cls):
        """Очистка."""
        session = cls.db_connection.connect(cls.config)
        if session:
            try:
                session.execute(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE")
                session.commit()
            finally:
                session.close()
    
    def test_import_then_export_preserves_content(self):
        """Тест: импорт затем экспорт сохраняет содержимое."""
        from src.domain.models.config import ExportConfig
        
        session = self.db_connection.connect(self.config)
        
        try:
            # Импортируем файл
            original_content = b"0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1027\n0\nENDSEC\n0\nEOF\n"
            
            file_id = self.repository.create_file(
                session,
                filename="cycle_test.dxf",
                file_content=original_content,
                schema_name=self.TEST_SCHEMA
            )
            
            session.commit()
            
        finally:
            session.close()
        
        # Экспортируем
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as f:
            temp_path = f.name
        
        try:
            config = ExportConfig(
                connection=self.config,
                file_id=file_id,
                destination="file",
                output_path=temp_path
            )
            
            result = self.export_service.export_from_database(config)
            
            self.assertTrue(result.success)
            
            # Проверяем что содержимое совпадает
            with open(temp_path, 'rb') as f:
                exported_content = f.read()
            
            self.assertEqual(original_content, exported_content)
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


# ========== Test Runner ==========

def run_integration_tests():
    """Запуск интеграционных тестов."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseConnectionIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestDxfRepositoryIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestImportServiceIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestExportServiceIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestFullImportExportCycle))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == '__main__':
    run_integration_tests()
