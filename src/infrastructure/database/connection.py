# -*- coding: utf-8 -*-
"""
Database Connection - управление подключениями к PostgreSQL.

Обеспечивает:
- Создание и переиспользование подключений
- Проверку расширения PostGIS
- Управление сессиями SQLAlchemy
"""

from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, close_all_sessions
from sqlalchemy.engine import Engine

from ...application.settings_service import ConnectionSettings
from ...logger.logger import Logger


class DatabaseConnection:
    """
    Управление подключением к PostgreSQL.
    
    Singleton с возможностью переподключения к разным БД.
    Не содержит бизнес-логики или UI-зависимостей.
    """
    
    DATABASE_URL_PATTERN = 'postgresql://{username}:{password}@{host}:{port}/{database}'
    CLIENT_ENCODING = 'WIN1251'
    
    _instance: Optional['DatabaseConnection'] = None
    _engine: Optional[Engine] = None
    _session_factory: Optional[sessionmaker] = None
    _current_settings: Optional[ConnectionSettings] = None
    
    def __new__(cls) -> 'DatabaseConnection':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def instance(cls) -> 'DatabaseConnection':
        """Получить экземпляр соединения (singleton)."""
        return cls()
    
    def connect(self, settings: ConnectionSettings) -> Optional[Session]:
        """
        Создать подключение к базе данных.
        
        Args:
            settings: Настройки подключения
            
        Returns:
            Session или None при ошибке
        """
        try:
            # Проверяем, нужно ли переподключаться
            if self._needs_reconnect(settings):
                self._close_existing()
                self._create_connection(settings)
            
            if self._session_factory is None:
                return None
                
            session = self._session_factory()
            Logger.log_message(
                f"Подключено к PostgreSQL '{settings.database}' "
                f"на {settings.host}:{settings.port}"
            )
            return session
            
        except Exception as e:
            Logger.log_error(
                f"Ошибка подключения к '{settings.database}' "
                f"на {settings.host}:{settings.port}: {str(e)}"
            )
            return None
    
    def get_session(self) -> Optional[Session]:
        """
        Получить сессию для текущего подключения.
        
        Returns:
            Session или None если не подключено
        """
        if self._session_factory is None:
            Logger.log_warning("Попытка получить сессию без активного подключения")
            return None
        return self._session_factory()
    
    def get_engine(self) -> Optional[Engine]:
        """Получить движок SQLAlchemy."""
        return self._engine
    
    def close(self) -> None:
        """Закрыть все соединения."""
        self._close_existing()
        Logger.log_message("Соединения с БД закрыты")
    
    def ensure_postgis_extension(self, session: Session) -> bool:
        """
        Проверить и при необходимости создать расширение PostGIS.
        
        Args:
            session: Активная сессия БД
            
        Returns:
            True если расширение доступно
        """
        try:
            with session.bind.connect() as connection:
                # Проверяем наличие расширения
                result = connection.execute(text("""
                    SELECT EXISTS(
                        SELECT 1 FROM pg_extension WHERE extname = 'postgis'
                    );
                """))
                
                if result.scalar():
                    Logger.log_message("Расширение PostGIS установлено")
                    return True
                
                # Пытаемся создать расширение
                Logger.log_message("Расширение PostGIS не найдено, создаём...")
                try:
                    connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                    connection.commit()
                    Logger.log_message("Расширение PostGIS успешно создано")
                    return True
                except Exception as create_error:
                    Logger.log_error(f"Не удалось создать PostGIS: {str(create_error)}")
                    return False
                    
        except Exception as e:
            Logger.log_error(f"Ошибка проверки PostGIS: {str(e)}")
            return False
    
    def test_connection(self, settings: ConnectionSettings) -> bool:
        """
        Проверить возможность подключения к БД.
        
        Args:
            settings: Настройки для проверки
            
        Returns:
            True если подключение успешно
        """
        try:
            session = self.connect(settings)
            if session is None:
                return False
            
            # Выполняем простой запрос
            session.execute(text("SELECT 1"))
            session.close()
            return True
            
        except Exception as e:
            Logger.log_error(f"Тест подключения не пройден: {str(e)}")
            return False
    
    # ========== Приватные методы ==========
    
    def _needs_reconnect(self, settings: ConnectionSettings) -> bool:
        """Проверить, требуется ли переподключение."""
        if self._current_settings is None:
            return True
        
        return (
            self._current_settings.host != settings.host or
            self._current_settings.port != settings.port or
            self._current_settings.database != settings.database or
            self._current_settings.username != settings.username or
            self._current_settings.password != settings.password
        )
    
    def _create_connection(self, settings: ConnectionSettings) -> None:
        """Создать новое подключение."""
        db_url = self.DATABASE_URL_PATTERN.format(
            username=settings.username,
            password=settings.password,
            host=settings.host,
            port=settings.port,
            database=settings.database
        )
        
        self._engine = create_engine(
            db_url,
            connect_args={'client_encoding': self.CLIENT_ENCODING}
        )
        self._session_factory = sessionmaker(
            autocommit=False, 
            autoflush=False, 
            bind=self._engine
        )
        self._current_settings = settings
    
    def _close_existing(self) -> None:
        """Закрыть существующие соединения."""
        if self._session_factory is not None:
            close_all_sessions()
        
        if self._engine is not None:
            self._engine.dispose()
        
        self._engine = None
        self._session_factory = None
        self._current_settings = None
