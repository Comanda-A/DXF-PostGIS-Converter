from __future__ import annotations

import psycopg2
from psycopg2.extensions import connection as pg_connection
from psycopg2.extras import RealDictCursor
from typing import Any, Optional
from ....domain.repositories import IConnection
from ....domain.value_objects import ConnectionConfig, Result, Unit


class PostGISConnection(IConnection):
    """Подключение к PostgreSQL/PostGIS"""

    def __init__(self):
        self._connection: Optional[pg_connection] = None
        self._config: Optional[ConnectionConfig] = None

    @property
    def db_type(self) -> str:
        return "PostgreSQL/PostGIS"

    @property
    def is_connected(self) -> bool:
        """Проверяет, установлено ли соединение с базой данных"""
        if self._connection is None:
            return False
        try:
            return not self._connection.closed
        except Exception:
            return False

    def connect(self, config: ConnectionConfig) -> Result[Unit]:
        """Установка соединения с PostgreSQL"""
        try:
            self._config = config

            conn_params = {
                'host': config.host,
                'port': config.port,
                'database': config.database,
                'user': config.username,
                'password': config.password
            }

            self._connection = psycopg2.connect(**conn_params)
            self._connection.autocommit = False

            # Установка PostGIS расширения - обязательно
            postgis_result = self._enable_postgis()
            if postgis_result.is_fail:
                self._connection = None
                return Result.fail(f"Failed to enable PostGIS extension: {postgis_result.error}")

            return Result.success(Unit())

        except Exception as e:
            self._connection = None
            return Result.fail(f"Failed to connect to PostgreSQL: {str(e).strip()}")

    def close(self) -> Result[Unit]:
        """Закрытие соединения"""
        try:
            if self.is_connected:
                self._connection.close()
            self._connection = None
            return Result.success(Unit())
        except Exception as e:
            self._connection = None
            return Result.fail(f"Failed to close connection: {str(e).strip()}")

    def commit(self) -> Result[Unit]:
        if not self.is_connected:
            return Result.fail("No active connection")
        try:
            self._connection.commit()
            return Result.success(Unit())
        except Exception as e:
            return Result.fail(str(e))

    def rollback(self) -> Result[Unit]:
        if not self.is_connected:
            return Result.fail("No active connection")
        try:
            self._connection.rollback()
            return Result.success(Unit())
        except Exception as e:
            return Result.fail(str(e))

    def _enable_postgis(self) -> Result[Unit]:
        """Включение расширения PostGIS"""
        if not self.is_connected:
            return Result.fail("No active connection to enable PostGIS")

        try:
            with self._connection.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
            self._connection.commit()
            return Result.success(Unit())
        except Exception as e:
            try:
                self._connection.rollback()
                return Result.fail(f"Failed to enable PostGIS: {str(e).strip()}")
            except Exception as e2:
                return Result.fail(f"Failed to enable PostGIS. {str(e).strip()}. {str(e2).strip()}")

    def get_connection(self) -> pg_connection | None:
        """Получение native соединения"""
        return self._connection

    def execute_query(self, query: str, params: tuple = ()) -> Result[list]:
        """Выполнение запроса"""
        if not self.is_connected:
            return Result.fail("No active database connection")

        try:
            with self._connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params if params else None)
                if cursor.description:  # SELECT запрос
                    rows = cursor.fetchall()
                    return Result.success(rows)
                else:
                    return Result.success([])
        except Exception as e:
            return Result.fail(f"Failed to execute query: {str(e).strip()}")

    def execute_queries(self, queries: list[tuple[str, Any]]) -> Result[Unit]:
        """Выполнение нескольких запросов в транзакции"""
        if not self.is_connected:
            return Result.fail("No active database connection")

        try:
            with self._connection.cursor() as cursor:
                for query, params in queries:
                    cursor.execute(query, params)
            return Result.success(Unit())
        except Exception as e:
            return Result.fail(f"Failed to execute transaction: {str(e).strip()}")

    def get_schemas(self) -> Result[list[str]]:
        """Список всех схем в базе данных"""
        if not self.is_connected:
            return Result.fail("No active database connection")

        query = """
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
            AND schema_name NOT LIKE 'pg_temp_%%'
            AND schema_name NOT LIKE 'pg_toast_temp_%%'
            ORDER BY schema_name
        """
        result = self.execute_query(query)
        if result.is_success:
            try:
                schemas = [row['schema_name'] for row in result.value]
                return Result.success(schemas)
            except (KeyError, TypeError, IndexError) as e:
                return Result.fail(f"Failed to parse schemas result: {str(e).strip()}")
        return Result.fail(f"Failed to get schemas: {result.error}")

    def schema_exists(self, schema_name: str) -> Result[bool]:
        """Проверка существования схемы"""
        if not self.is_connected:
            return Result.fail("No active database connection")

        query = """
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata 
                WHERE schema_name = %s
            ) as schema_exists
        """
        result = self.execute_query(query, (schema_name,))
        if result.is_success and result.value:
            try:
                exists = result.value[0]['schema_exists']
                return Result.success(bool(exists))
            except Exception as e:
                return Result.fail(f"Failed to parse schema_exists result: {str(e).strip()}")
        return Result.fail(
            f"Failed to check schema existence for '{schema_name}': "
            f"{result.error if not result.is_success else 'Empty result'}"
        )

    def create_schema(self, schema_name: str) -> Result[Unit]:
        """Создание схемы"""
        if not self.is_connected:
            return Result.fail("No active database connection")

        from psycopg2 import sql
        query = sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(
            sql.Identifier(schema_name)
        )

        if not self.is_connected:
            return Result.fail("No active database connection")

        try:
            with self._connection.cursor() as cursor:
                cursor.execute(query)
            self._connection.commit()
            return Result.success(Unit())
        except Exception as e:
            try:
                self._connection.rollback()
            except Exception:
                pass
            return Result.fail(f"Failed to create schema '{schema_name}': {str(e).strip()}")

    def drop_schema(self, schema_name: str, cascade: bool = False) -> Result[Unit]:
        """Удаляет схему"""
        if not self.is_connected:
            return Result.fail("No active database connection")

        exists_result = self.schema_exists(schema_name)
        if exists_result.is_success and not exists_result.value:
            return Result.fail(f"Schema '{schema_name}' does not exist")

        from psycopg2 import sql
        cascade_sql = sql.SQL(" CASCADE") if cascade else sql.SQL("")
        query = sql.SQL('DROP SCHEMA {}').format(
            sql.Identifier(schema_name)
        ) + cascade_sql

        try:
            with self._connection.cursor() as cursor:
                cursor.execute(query)
            self._connection.commit()
            return Result.success(Unit())
        except Exception as e:
            try:
                self._connection.rollback()
            except Exception:
                pass
            return Result.fail(f"Failed to drop schema '{schema_name}': {str(e).strip()}")

    def get_tables(self, schema_name: str) -> Result[list[str]]:
        """Список таблиц в схеме"""
        if not self.is_connected:
            return Result.fail("No active database connection")

        exists_result = self.schema_exists(schema_name)
        if exists_result.is_success and not exists_result.value:
            return Result.fail(f"Schema '{schema_name}' does not exist")

        query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        result = self.execute_query(query, (schema_name,))

        if result.is_success:
            try:
                tables = [row['table_name'] for row in result.value]
                return Result.success(tables)
            except (KeyError, TypeError, IndexError) as e:
                return Result.fail(f"Failed to parse tables result: {str(e).strip()}")
        return Result.fail(f"Failed to get tables from schema '{schema_name}': {result.error}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()