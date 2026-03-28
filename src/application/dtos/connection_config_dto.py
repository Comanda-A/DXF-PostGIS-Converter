
from dataclasses import dataclass

@dataclass
class ConnectionConfigDTO:
    """Настройки подключения к базе данных."""
    db_type: str
    name: str
    host: str
    port: str
    database: str
    username: str
    password: str
