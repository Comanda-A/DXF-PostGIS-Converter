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
            print("Connected to PostgreSQL database")
            self.create_tables_and_triggers()
            return True
        except OperationalError as e:
            print(f"Error connecting to PostgreSQL database: {e}")
            return False

    def create_tables_and_triggers(self):
        create_tables_query = """
        CREATE TABLE IF NOT EXISTS layer_sets (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS layers (
            id SERIAL PRIMARY KEY,
            layer_set_id INTEGER NOT NULL REFERENCES layer_sets(id) ON DELETE CASCADE,
            layer_name VARCHAR(255) NOT NULL,
            json_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_layer_set_id ON layers(layer_set_id);

        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
           NEW.updated_at = NOW();
           RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS update_layer_sets_updated_at ON layer_sets;
        CREATE TRIGGER update_layer_sets_updated_at
        BEFORE UPDATE ON layer_sets
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();

        DROP TRIGGER IF EXISTS update_layers_updated_at ON layers;
        CREATE TRIGGER update_layers_updated_at
        BEFORE UPDATE ON layers
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
        cursor = self.connection.cursor()
        cursor.execute(create_tables_query)
        self.connection.commit()
        cursor.close()

    def save_layer_set(self, name, description, layers):
        if not self.connection:
            print("No database connection.")
            return False

        try:
            cursor = self.connection.cursor()
            
            insert_layer_set_query = (
                "INSERT INTO layer_sets (name, description) VALUES (%s, %s) RETURNING id"
            )
            cursor.execute(insert_layer_set_query, (name, description))
            layer_set_id = cursor.fetchone()[0]

            insert_layer_query = (
                "INSERT INTO layers (layer_set_id, layer_name, json_data) VALUES (%s, %s, %s)"
            )
            for layer in layers:
                cursor.execute(insert_layer_query, (layer_set_id, layer['layer_name'], layer['json_data']))

            self.connection.commit()
            print("Layer set and layers saved successfully")
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