from abc import ABC, abstractmethod
from typing import Optional
from ...application.dtos import ConnectionConfigDTO


class IQgisConnectionProvider(ABC):
    """Интерфейс для получения подключений из QGIS."""
    
    @abstractmethod
    def get_qgis_connections(self) -> list[ConnectionConfigDTO]:
        """
        Получить все доступные подключения из QGIS.
        
        Returns:
            list[ConnectionConfigDTO]: Список подключений из QGIS.
        """
        pass
    
    @abstractmethod
    def get_qgis_connection_password(self, connection_name: str) -> Optional[str]:
        """
        Получить пароль для подключения из хранилища QGIS.
        
        Args:
            connection_name: Имя подключения в QGIS.
            
        Returns:
            str | None: Пароль или None если не найден.
        """
        pass
