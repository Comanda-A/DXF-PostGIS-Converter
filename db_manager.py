import psycopg2
from psycopg2 import OperationalError
from qgis.PyQt.QtWidgets import QMessageBox

class DBManager:
    def __init__(self, host, port, database, user, password, table_name):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.connection = None
        self.table_name = table_name

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
        create_tables_query = f"""
        CREATE TABLE IF NOT EXISTS layer_sets (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS {self.table_name} (
            id SERIAL PRIMARY KEY,
            layer_set_id INTEGER NOT NULL REFERENCES layer_sets(id) ON DELETE CASCADE,
            layer_name VARCHAR(255) NOT NULL,
            json_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_layer_set_id ON {self.table_name}(layer_set_id);

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

        DROP TRIGGER IF EXISTS update_layers_updated_at ON {self.table_name};
        CREATE TRIGGER update_layers_updated_at
        BEFORE UPDATE ON {self.table_name}
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
        cursor = self.connection.cursor()
        cursor.execute(create_tables_query)
        self.connection.commit()
        cursor.close()

    def table_exists(self, table_name):
        query = """
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = %s
            LIMIT 2
        );
        """
        cursor = self.connection.cursor()
        cursor.execute(query, (table_name,))
        exists = cursor.fetchone()[0]
        cursor.close()
        return exists

    def save_layer_set(self, name, description, layers, table_name=None, truncate=False):
        if not self.connection:
            print("No database connection.")
            return False

        self.table_name = table_name
        try:
            cursor = self.connection.cursor()

            if table_name and self.table_exists(table_name):
                if truncate:
                    print(f"Truncating existing table '{table_name}' and inserting new data.")
                    message = "Перезаписать существующую таблицу?"

                    reply = QMessageBox.question(None, 'Попытка перезаписи', message,
                                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

                    if reply == QMessageBox.No:
                        return
                    truncate_query = f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE;"
                    cursor.execute(truncate_query)

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

            
                else:
                    print(f"Saving data into existing table '{table_name}'")
                    
                    message = "Перезаписать поля существующей таблицы?"

                    reply = QMessageBox.question(None, 'Попытка перезаписи', message,
                                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

                    if reply == QMessageBox.No:
                        return
                    update_layer_query = (
                        "UPDATE layers SET json_data = %s, updated_at = CURRENT_TIMESTAMP "
                        "WHERE layer_name = %s"
                    )
                    for layer in layers:
                        cursor.execute(update_layer_query, (layer['json_data'], layer['layer_name']))

            else:
                print(f"Creating new layer set and saving data.")
            self.create_tables_and_triggers()

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