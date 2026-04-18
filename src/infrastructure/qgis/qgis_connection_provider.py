from __future__ import annotations
from typing import Optional
from ...application.interfaces import IQgisConnectionProvider
from ...application.dtos import ConnectionConfigDTO
from ...application.interfaces import ILogger


class QgisConnectionProvider(IQgisConnectionProvider):
    """Реализация провайдера для получения подключений из QGIS."""
    
    def __init__(self, logger: ILogger):
        """
        Инициализация провайдера.
        
        Args:
            logger: Логгер для записи ошибок и информации.
        """
        self._logger = logger
    
    def get_qgis_connections(self) -> list[ConnectionConfigDTO]:
        """
        Получить все доступные подключения из QGIS.
        
        Returns:
            list[ConnectionConfigDTO]: Список подключений из QGIS.
        """
        try:
            # Получаем список имен подключений PostgreSQL/PostGIS
            postgres_connections = self._get_postgres_connections()
            
            self._logger.message(f"Found {len(postgres_connections)} QGIS connections")
            
            return postgres_connections
            
        except Exception as e:
            self._logger.error(f"Error getting QGIS connections: {str(e)}")
            return []
    
    def _get_postgres_connections(self) -> list[ConnectionConfigDTO]:
        """Получить подключения PostgreSQL из QGIS."""
        connections = []
        
        try:
            from qgis.PyQt.QtCore import QSettings
            
            settings = QSettings()
            settings.beginGroup('PostgreSQL/connections')
            
            connection_names = settings.childGroups()
            
            for conn_name in connection_names:
                settings.beginGroup(conn_name)
                
                # Читаем параметры подключения
                host = settings.value('host', '')
                port = settings.value('port', '5432')
                database = settings.value('database', '')
                username = settings.value('username', '')
                
                settings.endGroup()
                
                # Создаем DTO подключения если есть минимальные параметры
                if host and database:
                    connection = ConnectionConfigDTO(
                        db_type='PostgreSQL/PostGIS',
                        name=conn_name,
                        host=host,
                        port=str(port),
                        database=database,
                        username=username,
                        password=''  # Пароль будет запрошен позже
                    )
                    connections.append(connection)
                    self._logger.message(f"Loaded QGIS connection: {conn_name}")
            
            settings.endGroup()
            
        except Exception as e:
            self._logger.error(f"Error reading PostgreSQL connections from QGIS: {str(e)}")
        
        return connections
    
    def get_qgis_connection_password(self, connection_name: str) -> Optional[str]:
        """
        Получить пароль для подключения из хранилища QGIS.
        
        Примечание: QGIS обычно не хранит пароли открыто в безопасных целях.
        Возвращает None в большинстве случаев.
        
        Args:
            connection_name: Имя подключения в QGIS.
            
        Returns:
            str | None: Пароль или None.
        """
        try:
            from qgis.PyQt.QtCore import QSettings
            
            settings = QSettings()
            settings.beginGroup(f'PostgreSQL/connections/{connection_name}')
            
            # QGIS может хранить пароль если это явно разрешено
            password = settings.value('password', '')
            
            settings.endGroup()
            
            return password if password else None
            
        except Exception as e:
            self._logger.warning(f"Could not retrieve password for {connection_name}: {str(e)}")
            return None
