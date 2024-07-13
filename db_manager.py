import mysql.connector
from mysql.connector import Error

class DBManager:
    def __init__(self, host, port, database, user, password):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.connection = None

    def connect(self):
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            if self.connection.is_connected():
                print("Connected to MySQL database")
                return True
            else:
                print("Connection failed")
                return False
        except Error as e:
            print(f"Error connecting to MySQL database: {e}")
            return False

    def save_selected_objects(self, selected_objects):
        if not self.connection:
            print("No database connection.")
            return False

        try:
            cursor = self.connection.cursor()
            for obj in selected_objects:
                insert_query = (
                    "INSERT INTO selected_objects (layer, entity_type, attributes, geometry) "
                    "VALUES (%s, %s, %s, %s)"
                )
                cursor.execute(insert_query, (obj['layer'], obj['entity_type'], obj['attributes'], obj['geometry']))
            self.connection.commit()
            print("Data saved successfully")
            return True
        except Error as e:
            print(f"Error saving data: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def close(self):
        if self.connection:
            self.connection.close()
            print("MySQL connection closed")