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
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker

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
        database=os.environ.get('TEST_DB_NAME', 'postgres'),
        username=os.environ.get('TEST_DB_USER', 'postgres'),
        password=os.environ.get('TEST_DB_PASSWORD', '123')
    )


def get_direct_session():
    """Создать прямое SQLAlchemy соединение без использования Singleton."""
    config = get_test_db_config()
    db_url = f'postgresql://{config.username}:{config.password}@{config.host}:{config.port}/{config.database}'
    
    try:
        # Добавляем pool_pre_ping и ограничиваем пул для тестов
        engine = create_engine(
            db_url, 
            connect_args={'client_encoding': 'WIN1251'},
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0,
            pool_timeout=10
        )
        Session = sessionmaker(bind=engine)
        session = Session()
        # Проверяем соединение
        session.execute(text("SELECT 1"))
        print("  Подключение успешно!")
        return session, engine
    except Exception as e:
        print(f"  ОШИБКА подключения: {type(e).__name__}: {e}")
        return None, None


def reset_db_connection_singleton():
    """Сбросить Singleton DatabaseConnection для чистого теста."""
    from src.infrastructure.database import DatabaseConnection
    
    # Сначала закрываем все соединения
    if DatabaseConnection._engine is not None:
        try:
            from sqlalchemy.orm import close_all_sessions
            close_all_sessions()
            DatabaseConnection._engine.dispose()
        except Exception:
            pass
    
    DatabaseConnection._instance = None
    DatabaseConnection._engine = None
    DatabaseConnection._session_factory = None
    DatabaseConnection._current_settings = None


def skip_if_no_db():
    """Декоратор для пропуска тестов если БД недоступна."""
    session, engine = get_direct_session()
    if session:
        session.close()
        engine.dispose()
        return lambda f: f  # Не пропускать
    return unittest.skip("Database not available")


class TestDatabaseConnectionIntegration(unittest.TestCase):
    """Интеграционные тесты DatabaseConnection."""
    
    @classmethod
    def setUpClass(cls):
        """Проверка доступности БД."""
        # Сбрасываем singleton перед тестами
        reset_db_connection_singleton()
        
        # Сначала проверяем прямым соединением
        session, engine = get_direct_session()
        if not session:
            raise unittest.SkipTest("Cannot connect to test database")
        session.close()
        engine.dispose()
        
        from src.infrastructure.database import DatabaseConnection
        cls.db_connection = DatabaseConnection()
        cls.config = get_test_db_config()
    
    @classmethod
    def tearDownClass(cls):
        """Очистка после тестов."""
        reset_db_connection_singleton()
    
    def test_connect_and_disconnect(self):
        """Тест подключения и отключения."""
        session = self.db_connection.connect(self.config)
        
        self.assertIsNotNone(session)
        
        # Проверяем что сессия рабочая
        result = session.execute(text("SELECT 1")).scalar()
        self.assertEqual(result, 1)
        
        session.close()
    
    def test_test_connection(self):
        """Тест метода test_connection."""
        success = self.db_connection.test_connection(self.config)
        
        self.assertTrue(success)

    def test_ensure_postgis_extension(self):
        """Тест создания PostGIS расширения."""
        session = self.db_connection.connect(self.config)
        self.assertIsNotNone(session, "Failed to connect to database")
        
        try:
            self.db_connection.ensure_postgis_extension(session)
            
            # Проверяем что PostGIS доступен
            result = session.execute(text("SELECT PostGIS_Version()")).scalar()
            
            self.assertIsNotNone(result)
            
        finally:
            session.close()


class TestDxfRepositoryIntegration(unittest.TestCase):
    """Интеграционные тесты DxfRepository."""
    
    TEST_SCHEMA = 'test_dxf_integration'
    
    @classmethod
    def setUpClass(cls):
        """Настройка тестовой схемы."""
        # Сбрасываем singleton
        reset_db_connection_singleton()
        
        # Проверяем доступность БД прямым соединением
        session, engine = get_direct_session()
        if not session:
            raise unittest.SkipTest("Cannot connect to test database")
        
        try:
            # Создаём тестовую схему напрямую
            session.execute(text(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE"))
            session.execute(text(f"CREATE SCHEMA {cls.TEST_SCHEMA}"))
            session.commit()
        finally:
            session.close()
            engine.dispose()
        
        from src.infrastructure.database import DatabaseConnection, DxfRepository
        
        cls.db_connection = DatabaseConnection()
        cls.config = get_test_db_config()
        cls.repository = DxfRepository(cls.db_connection)
    
    @classmethod
    def tearDownClass(cls):
        """Удаление тестовой схемы."""
        session, engine = get_direct_session()
        if session:
            try:
                session.execute(text(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE"))
                session.commit()
            finally:
                session.close()
                engine.dispose()
        reset_db_connection_singleton()
    
    def test_create_and_get_file(self):
        """Тест создания и получения файла."""
        session = self.db_connection.connect(self.config)
        
        try:
            # Создаём файл
            test_content = b"TEST DXF CONTENT"
            file_record = self.repository.create_file(
                session,
                filename="test_file.dxf",
                content=test_content,
                schema=self.TEST_SCHEMA
            )
            
            self.assertIsNotNone(file_record)
            self.assertIsNotNone(file_record.id)
            
            # Получаем файл
            retrieved = self.repository.get_file_by_id(session, file_record.id, self.TEST_SCHEMA)
            
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.filename, "test_file.dxf")
            self.assertEqual(retrieved.file_content, test_content)
            
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
                    content=f"CONTENT {i}".encode(),
                    schema=self.TEST_SCHEMA
                )
            
            # Получаем список
            files = self.repository.get_all_files(session, schema=self.TEST_SCHEMA)
            
            self.assertGreaterEqual(len(files), 3)
            
        finally:
            session.close()
    
    def test_delete_file(self):
        """Тест удаления файла."""
        session = self.db_connection.connect(self.config)
        
        try:
            # Создаём файл
            file_record = self.repository.create_file(
                session,
                filename="to_delete.dxf",
                content=b"DELETE ME",
                schema=self.TEST_SCHEMA
            )
            
            # Сохраняем ID до удаления
            file_id = file_record.id
            
            # Удаляем
            self.repository.delete_file(session, file_id, self.TEST_SCHEMA)
            
            # Проверяем что удалён
            retrieved = self.repository.get_file_by_id(session, file_id, self.TEST_SCHEMA)
            self.assertIsNone(retrieved)
            
        finally:
            session.close()
    
    def test_create_layer_table(self):
        """Тест создания таблицы слоя."""
        session = self.db_connection.connect(self.config)
        
        try:
            layer_name = "test_layer"
            
            self.repository.create_layer_table(
                session, 
                layer_name=layer_name, 
                layer_schema=self.TEST_SCHEMA,
                file_schema=self.TEST_SCHEMA
            )
            
            # Проверяем что таблица создана
            result = session.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = '{self.TEST_SCHEMA}'
                    AND table_name = '{layer_name}'
                )
            """)).scalar()
            
            self.assertTrue(result)
            
        finally:
            session.close()


class TestImportServiceIntegration(unittest.TestCase):
    """Интеграционные тесты ImportService."""
    
    TEST_SCHEMA = 'test_import_integration'
    
    @classmethod
    def setUpClass(cls):
        """Настройка."""
        reset_db_connection_singleton()
        
        # Проверяем доступность БД прямым соединением
        session, engine = get_direct_session()
        if not session:
            raise unittest.SkipTest("Cannot connect to test database")
        
        try:
            session.execute(text(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE"))
            session.execute(text(f"CREATE SCHEMA {cls.TEST_SCHEMA}"))
            session.commit()
        finally:
            session.close()
            engine.dispose()
        
        from src.infrastructure.database import DatabaseConnection, DxfRepository
        from src.application.import_service import ImportService
        
        cls.db_connection = DatabaseConnection()
        cls.config = get_test_db_config()
        cls.repository = DxfRepository(cls.db_connection)
        cls.import_service = ImportService(
            connection=cls.db_connection,
            repository=cls.repository
        )
    
    @classmethod
    def tearDownClass(cls):
        """Очистка."""
        session, engine = get_direct_session()
        if session:
            try:
                session.execute(text(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE"))
                session.commit()
            finally:
                session.close()
                engine.dispose()
        reset_db_connection_singleton()
    
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
    test_file_id = None
    
    @classmethod
    def setUpClass(cls):
        """Настройка."""
        reset_db_connection_singleton()
        
        # Проверяем доступность БД прямым соединением
        session, engine = get_direct_session()
        if not session:
            raise unittest.SkipTest("Cannot connect to test database")
        
        try:
            session.execute(text(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE"))
            session.execute(text(f"CREATE SCHEMA {cls.TEST_SCHEMA}"))
            session.commit()
        finally:
            session.close()
            engine.dispose()
        
        from src.infrastructure.database import DatabaseConnection, DxfRepository
        from src.application.export_service import ExportService
        
        cls.db_connection = DatabaseConnection()
        cls.config = get_test_db_config()
        cls.repository = DxfRepository(cls.db_connection)
        cls.export_service = ExportService(
            db_connection=cls.db_connection,
            repository=cls.repository
        )
        
        # Создаём тестовый файл
        session = cls.db_connection.connect(cls.config)
        if session:
            try:
                file_record = cls.repository.create_file(
                    session,
                    filename="export_test.dxf",
                    content=b"0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n",
                    schema=cls.TEST_SCHEMA
                )
                cls.test_file_id = file_record.id if file_record else None
                session.commit()
            finally:
                session.close()
    
    @classmethod
    def tearDownClass(cls):
        """Очистка."""
        session, engine = get_direct_session()
        if session:
            try:
                session.execute(text(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE"))
                session.commit()
            finally:
                session.close()
                engine.dispose()
        reset_db_connection_singleton()
    
    def test_validate_export_config_valid(self):
        """Тест валидации корректной конфигурации экспорта."""
        from src.domain.models.config import ExportConfig
        
        config = ExportConfig(
            connection=self.config,
            file_id=self.test_file_id,
            destination="qgis",
            file_schema=self.TEST_SCHEMA
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
                output_path=temp_path,
                file_schema=self.TEST_SCHEMA
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
        reset_db_connection_singleton()
        
        # Проверяем доступность БД прямым соединением
        session, engine = get_direct_session()
        if not session:
            raise unittest.SkipTest("Cannot connect to test database")
        
        try:
            session.execute(text(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE"))
            session.execute(text(f"CREATE SCHEMA {cls.TEST_SCHEMA}"))
            session.commit()
        finally:
            session.close()
            engine.dispose()
        
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
    
    @classmethod
    def tearDownClass(cls):
        """Очистка."""
        session, engine = get_direct_session()
        if session:
            try:
                session.execute(text(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE"))
                session.commit()
            finally:
                session.close()
                engine.dispose()
        reset_db_connection_singleton()
    
    def test_import_then_export_preserves_content(self):
        """Тест: импорт затем экспорт сохраняет содержимое."""
        from src.domain.models.config import ExportConfig
        
        session = self.db_connection.connect(self.config)
        
        try:
            # Импортируем файл
            original_content = b"0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1027\n0\nENDSEC\n0\nEOF\n"
            
            file_record = self.repository.create_file(
                session,
                filename="cycle_test.dxf",
                content=original_content,
                schema=self.TEST_SCHEMA
            )
            file_id = file_record.id if file_record else None
            
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
                output_path=temp_path,
                file_schema=self.TEST_SCHEMA
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


class TestRealDxfFileImport(unittest.TestCase):
    """Интеграционные тесты с реальными DXF файлами."""
    
    TEST_SCHEMA = 'test_real_dxf_import'
    
    @classmethod
    def setUpClass(cls):
        """Настройка."""
        reset_db_connection_singleton()
        
        # Проверяем доступность БД прямым соединением
        session, engine = get_direct_session()
        if not session:
            raise unittest.SkipTest("Cannot connect to test database")
        
        try:
            session.execute(text(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE"))
            session.execute(text(f"CREATE SCHEMA {cls.TEST_SCHEMA}"))
            session.commit()
        finally:
            session.close()
            engine.dispose()
        
        from src.infrastructure.database import DatabaseConnection, DxfRepository
        from src.application.import_service import ImportService
        
        cls.db_connection = DatabaseConnection()
        cls.config = get_test_db_config()
        cls.repository = DxfRepository(cls.db_connection)
        cls.import_service = ImportService(
            connection=cls.db_connection,
            repository=cls.repository
        )
        
        # Путь к тестовым DXF файлам
        cls.dxf_examples_dir = Path(__file__).parent.parent / 'dxf_examples'
        cls.test_files = {
            'example': cls.dxf_examples_dir / 'example.dxf',
            'ex1': cls.dxf_examples_dir / 'ex1.dxf',
            'ex2': cls.dxf_examples_dir / 'ex2.dxf',
            'simple_line': cls.dxf_examples_dir / 'simple_line.dxf',
        }
    
    @classmethod
    def tearDownClass(cls):
        """Очистка."""
        session, engine = get_direct_session()
        if session:
            try:
                session.execute(text(f"DROP SCHEMA IF EXISTS {cls.TEST_SCHEMA} CASCADE"))
                session.commit()
            finally:
                session.close()
                engine.dispose()
        reset_db_connection_singleton()
    
    def _get_available_test_file(self):
        """Получить первый доступный тестовый файл."""
        for name, path in self.test_files.items():
            if path.exists():
                return name, path
        return None, None
    
    def test_import_full_dxf_file(self):
        """Тест: импорт целого DXF файла со всеми слоями."""
        from src.domain.models.config import ImportConfig
        from src.domain.dxf import DxfDocument
        
        file_name, file_path = self._get_available_test_file()
        if not file_path:
            self.skipTest("No test DXF files available")
        
        # Загружаем DXF
        doc = DxfDocument(str(file_path))
        self.assertTrue(doc.is_loaded, f"Cannot load DXF file: {file_path}")
        
        # Получаем информацию о слоях
        layers = doc.get_layers()
        total_layers = len(layers)
        total_entities = sum(len(entities) for entities in layers.values())
        
        print(f"\n  Testing full import of '{file_name}':")
        print(f"    Layers: {total_layers}")
        print(f"    Total entities: {total_entities}")
        
        # Конфигурация импорта
        config = ImportConfig(
            connection=self.config,
            layer_schema=self.TEST_SCHEMA,
            file_schema=self.TEST_SCHEMA,
            export_layers_only=False,
            mapping_mode='always_overwrite'
        )
        
        # Импортируем
        result = self.import_service.import_dxf(
            file_path=str(file_path),
            config=config
        )
        
        # Проверяем результат
        self.assertTrue(result.success, f"Import failed: {result.message}")
        self.assertGreater(result.layers_imported, 0, "No layers imported")
        self.assertEqual(result.files_imported, 1, "File not saved")
        
        print(f"    Imported layers: {result.layers_imported}")
        print(f"    Imported entities: {result.entities_imported}")
        
        # Проверяем что данные в базе
        session = self.db_connection.connect(self.config)
        try:
            count_result = session.execute(text(f"""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = '{self.TEST_SCHEMA}'
                AND table_type = 'BASE TABLE'
            """)).scalar()
            
            # Должны быть таблицы слоёв + таблица dxf_files
            self.assertGreater(count_result, 0, "No tables created")
            
        finally:
            session.close()
    
    def test_import_selected_layers_only(self):
        """Тест: импорт только выбранных слоёв (не всех)."""
        from src.domain.models.config import ImportConfig
        from src.domain.dxf import DxfDocument
        
        file_name, file_path = self._get_available_test_file()
        if not file_path:
            self.skipTest("No test DXF files available")
        
        # Загружаем DXF
        doc = DxfDocument(str(file_path))
        self.assertTrue(doc.is_loaded)
        
        # Получаем информацию о слоях
        all_layers = doc.get_layers()
        layer_names = list(all_layers.keys())
        
        if len(layer_names) < 2:
            self.skipTest(f"DXF file has only {len(layer_names)} layer(s), need at least 2")
        
        # Выбираем только первую половину слоёв
        selected_layer_names = layer_names[:len(layer_names)//2 + 1]
        selected_layers = {
            name: all_layers[name] for name in selected_layer_names
        }
        
        print(f"\n  Testing selected layers import of '{file_name}':")
        print(f"    Total layers in file: {len(layer_names)}")
        print(f"    Selected layers: {len(selected_layer_names)}")
        print(f"    Selected layer names: {selected_layer_names}")
        
        # Конфигурация импорта
        config = ImportConfig(
            connection=self.config,
            layer_schema=self.TEST_SCHEMA,
            file_schema=self.TEST_SCHEMA,
            export_layers_only=True,  # Не сохраняем файл
            mapping_mode='always_overwrite'
        )
        
        # Импортируем только выбранные слои
        result = self.import_service.import_dxf(
            file_path=str(file_path),
            config=config,
            entities_by_layer=selected_layers
        )
        
        # Проверяем результат
        self.assertTrue(result.success, f"Import failed: {result.message}")
        self.assertEqual(result.layers_imported, len(selected_layer_names), 
                        "Wrong number of layers imported")
        self.assertEqual(result.files_imported, 0, "File should not be saved")
        
        print(f"    Imported layers: {result.layers_imported}")
        print(f"    Imported entities: {result.entities_imported}")
    
    def test_import_random_entities_from_layers(self):
        """Тест: импорт случайных объектов из нескольких слоёв (не всех)."""
        import random
        from src.domain.models.config import ImportConfig
        from src.domain.dxf import DxfDocument
        
        file_name, file_path = self._get_available_test_file()
        if not file_path:
            self.skipTest("No test DXF files available")
        
        # Загружаем DXF
        doc = DxfDocument(str(file_path))
        self.assertTrue(doc.is_loaded)
        
        # Получаем информацию о слоях
        all_layers = doc.get_layers()
        layer_names = list(all_layers.keys())
        
        if len(layer_names) < 2:
            self.skipTest(f"DXF file has only {len(layer_names)} layer(s), need at least 2")
        
        # Выбираем случайные слои (не все)
        num_layers_to_select = max(1, len(layer_names) // 2)
        selected_layer_names = random.sample(layer_names, num_layers_to_select)
        
        # Для каждого выбранного слоя берём случайные объекты
        entities_subset = {}
        total_selected = 0
        
        for layer_name in selected_layer_names:
            entities = all_layers[layer_name]
            if not entities:
                continue
            
            # Берём 30-70% объектов случайным образом
            sample_size = max(1, int(len(entities) * random.uniform(0.3, 0.7)))
            sample_size = min(sample_size, len(entities))
            selected_entities = random.sample(list(entities), sample_size)
            
            entities_subset[layer_name] = selected_entities
            total_selected += len(selected_entities)
        
        if not entities_subset:
            self.skipTest("No entities to import")
        
        print(f"\n  Testing random entities import of '{file_name}':")
        print(f"    Total layers in file: {len(layer_names)}")
        print(f"    Selected layers: {len(entities_subset)}")
        print(f"    Total entities selected: {total_selected}")
        
        for layer_name, entities in entities_subset.items():
            print(f"      {layer_name}: {len(entities)} entities")
        
        # Конфигурация импорта
        config = ImportConfig(
            connection=self.config,
            layer_schema=self.TEST_SCHEMA,
            file_schema=self.TEST_SCHEMA,
            export_layers_only=True,
            mapping_mode='always_overwrite'
        )
        
        # Импортируем подмножество
        result = self.import_service.import_dxf(
            file_path=str(file_path),
            config=config,
            entities_by_layer=entities_subset
        )
        
        # Проверяем результат
        self.assertTrue(result.success, f"Import failed: {result.message}")
        self.assertEqual(result.layers_imported, len(entities_subset),
                        "Wrong number of layers imported")
        
        # Количество импортированных объектов должно быть <= выбранных
        # (могут быть неконвертируемые типы)
        self.assertLessEqual(result.entities_imported, total_selected,
                            "Too many entities imported")
        
        print(f"    Result: {result.layers_imported} layers, {result.entities_imported} entities")
    
    def test_import_single_layer(self):
        """Тест: импорт одного конкретного слоя."""
        from src.domain.models.config import ImportConfig
        from src.domain.dxf import DxfDocument
        
        file_name, file_path = self._get_available_test_file()
        if not file_path:
            self.skipTest("No test DXF files available")
        
        # Загружаем DXF
        doc = DxfDocument(str(file_path))
        self.assertTrue(doc.is_loaded)
        
        # Получаем первый слой
        all_layers = doc.get_layers()
        if not all_layers:
            self.skipTest("No layers in DXF file")
        
        layer_name = list(all_layers.keys())[0]
        entities = all_layers[layer_name]
        
        print(f"\n  Testing single layer import of '{file_name}':")
        print(f"    Layer: {layer_name}")
        print(f"    Entities: {len(entities)}")
        
        # Импортируем только этот слой
        single_layer = {layer_name: entities}
        
        config = ImportConfig(
            connection=self.config,
            layer_schema=self.TEST_SCHEMA,
            file_schema=self.TEST_SCHEMA,
            export_layers_only=True,
            mapping_mode='always_overwrite'
        )
        
        result = self.import_service.import_dxf(
            file_path=str(file_path),
            config=config,
            entities_by_layer=single_layer
        )
        
        self.assertTrue(result.success, f"Import failed: {result.message}")
        self.assertEqual(result.layers_imported, 1, "Should import exactly 1 layer")
        
        print(f"    Imported: {result.entities_imported} entities")
    
    def test_import_all_available_files(self):
        """Тест: импорт всех доступных тестовых DXF файлов."""
        from src.domain.models.config import ImportConfig
        from src.domain.dxf import DxfDocument
        
        available_files = [
            (name, path) for name, path in self.test_files.items() 
            if path.exists()
        ]
        
        if not available_files:
            self.skipTest("No test DXF files available")
        
        print(f"\n  Testing import of all available DXF files:")
        
        total_imports = 0
        total_errors = 0
        
        for file_name, file_path in available_files:
            # Загружаем DXF
            doc = DxfDocument(str(file_path))
            if not doc.is_loaded:
                print(f"    SKIP {file_name}: Cannot load")
                continue
            
            layers = doc.get_layers()
            print(f"    {file_name}: {len(layers)} layers, {doc.get_entity_count()} entities")
            
            # Конфигурация
            config = ImportConfig(
                connection=self.config,
                layer_schema=self.TEST_SCHEMA,
                file_schema=self.TEST_SCHEMA,
                export_layers_only=True,  # Только слои, без файла
                mapping_mode='always_overwrite',
                custom_filename=f"test_{file_name}"
            )
            
            # Импортируем
            result = self.import_service.import_dxf(
                file_path=str(file_path),
                config=config
            )
            
            if result.success:
                total_imports += 1
                print(f"      OK: {result.layers_imported} layers, {result.entities_imported} entities")
            else:
                total_errors += 1
                print(f"      FAIL: {result.message}")
        
        print(f"    Total: {total_imports} successful, {total_errors} failed")
        
        self.assertGreater(total_imports, 0, "At least one file should import successfully")


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
    suite.addTests(loader.loadTestsFromTestCase(TestRealDxfFileImport))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == '__main__':
    run_integration_tests()
