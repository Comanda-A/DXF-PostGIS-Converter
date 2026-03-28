
from dataclasses import dataclass

@dataclass(frozen=True)
class ConnectionConfig:
    """Настройки подключения к базе данных."""
    db_type: str    # Тип СУБД 
    name: str       # Название соединения
    host: str       # Хост       
    port: str       # Порт
    database: str   # Имя БД
    username: str   # Имя пользователя
    password: str   # Пароль
