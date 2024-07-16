import psycopg2
from psycopg2 import OperationalError

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
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            self.create_table_if_not_exists()
            print("Connected to PostgreSQL database")
            return True
        except OperationalError as e:
            print(f"Error connecting to PostgreSQL database: {e}")
            return False

    def create_table_if_not_exists(self):
        create_table_query = """
        CREATE TABLE IF NOT EXISTS selected_objects (
            id SERIAL PRIMARY KEY,
            layer VARCHAR(255),
            entities VARCHAR(255),
            attributes TEXT,
            geometry TEXT
        );
        """
        cursor = self.connection.cursor()
        cursor.execute(create_table_query)
        self.connection.commit()
        cursor.close()

    def save_selected_objects(self, selected_objects):
        if not self.connection:
            print("No database connection.")
            return False

        try:
            cursor = self.connection.cursor()
            for obj in selected_objects:
                layer = obj['layer']
                entities = obj['entities']
                attributes = ', '.join(obj['attributes'])
                geometry = ', '.join(obj['geometry'])
                
                insert_query = (
                    "INSERT INTO selected_objects (layer, entities, attributes, geometry) "
                    "VALUES (%s, %s, %s, %s)"
                )
                cursor.execute(insert_query, (layer, entities, attributes, geometry))
            self.connection.commit()
            print("Data saved successfully")
            return True
        except OperationalError as e:
            print(f"Error saving data: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def close(self):
        if self.connection:
            self.connection.close()
            print("PostgreSQL connection closed")