

'''
Скрипт управляет сохранением, загрузкой и обновлением подключений к базам данных для плагина. 
Он сохраняет данные о подключениях (пользователь, пароль, имя подключения) в 
локальный файл db_connections.json, который хранится в директории ~/Documents/DXF-PostGIS-Converter.
'''

from ..logger.logger import Logger  # Импорт логгера для записи сообщений

import os
import json

# Определяем путь к директории и файлу для хранения подключений
DIRECTORY = os.path.expanduser("~/Documents/DXF-PostGIS-Converter")
FILENAME = "db_connections.json"
FILEPATH = os.path.join(DIRECTORY, FILENAME)

# Создаем директорию, если она не существует
os.makedirs(DIRECTORY, exist_ok=True)

# Словарь для хранения всех подключений
db_connections = {}

# Список функций, которые будут вызваны при изменении подключения
event_db_connections_edited = []


# Вызов всех зарегистрированных обработчиков изменений подключения
def _call_event_db_connection_changed():
    for action in event_db_connections_edited:
        action()  # Вызываем каждую зарегистрированную функцию


# Функция для загрузки подключений из файла в память
def load_connections():
    global db_connections
    if os.path.exists(FILEPATH):  # Проверяем, существует ли файл
        with open(FILEPATH, 'r') as file:
            db_connections = json.load(file)  # Загружаем подключения из файла
    else:
        db_connections = {}  # Если файла нет, создаем пустой словарь
    _call_event_db_connection_changed()  # Вызываем событие изменения подключения


# Функция для сохранения подключений в файл
def save_connections():
    with open(FILEPATH, 'w') as file:
        json.dump(db_connections, file, indent=4)  # Сохраняем словарь подключений в файл с отступами


# Функция для добавления нового подключения
def add_connection(connection_name, username, password):
    # Добавляем новое подключение в словарь
    db_connections[connection_name] = {
        'username': username,
        'password': password
    }
    save_connections()  # Сохраняем обновленные подключения
    _call_event_db_connection_changed()  # Вызываем событие изменения подключения
    Logger.log_message(f"Connection '{connection_name}' saved successfully.")  # Логируем успешное сохранение


# Функция для получения подключения по имени базы данных
def get_connection(connection_name):
    global db_connections
    return db_connections.get(connection_name)  # Возвращаем подключение, если оно есть, иначе None


# Функция для получения всех сохраненных подключений
def get_all_connections():
    ''' Вернет словарь всех сохраненных подключений. '''
    global db_connections
    return db_connections


# Функция для удаления подключения по имени базы данных
def delete_connection(connection_name):
    global db_connections
    if connection_name in db_connections:  # Проверяем, существует ли подключение
        del db_connections[connection_name]  # Удаляем подключение из словаря
        save_connections()  # Сохраняем изменения
        _call_event_db_connection_changed()  # Вызываем событие изменения подключения


def edit_connection_via_dialog(connection_name):
    from ..gui.db_connection_dialog import DBConnectionDialog
    dlg = DBConnectionDialog(connection_name)



# Загружаем подключения при инициализации
load_connections()