from __future__ import annotations

import re

from ...domain.value_objects import Result, Unit, ConnectionConfig
from ...domain.repositories import (
    IConnectionFactory,
    IRepositoryFactory,
    IConnection,
    IContentRepository,
    IDocumentRepository,
    ILayerRepository,
    IEntityRepository
)

from ...application.dtos import ConnectionConfigDTO
from ...application.results import AppResult, Unit
from ...application.interfaces import ILogger

class DBSession:
    
    def __init__(
        self,
        connection_factory: IConnectionFactory,
        repository_factory: IRepositoryFactory,
        logger: ILogger
    ):
        self._connection_factory = connection_factory
        self._repository_factory = repository_factory
        self._logger = logger
        self._connection: IConnection | None = None
        self._config: ConnectionConfigDTO | None = None
    
    @property
    def is_connected(self) -> bool:
        return self._connection.is_connected if self._connection else False
    
    @property
    def config(self) -> ConnectionConfigDTO | None:
        return self._config

    def connect(self, config: ConnectionConfigDTO) -> AppResult[Unit]:
        self.close()

        result = self._connection_factory.get_connection(config.db_type)

        if result.is_fail:
            error_msg = f"Failed to get connection for db_type='{config.db_type}'. {result.error}"
            self._logger.error(error_msg)
            return AppResult.fail(error_msg)
        
        connection = result.value

        connection_result = connection.connect(
            ConnectionConfig(
                config.db_type,
                config.name,
                config.host,
                config.port,
                config.database,
                config.username,
                config.password
            )
        )

        if connection_result.is_success:
            self._config = config
            self._connection = connection
            return AppResult.success(Unit())
        else:
            error_msg = f"Connection failed. {connection_result.error}"
            self._logger.warning(error_msg)
            return AppResult.fail(error_msg)

    def close(self) -> AppResult[Unit]:
        result: Result[Unit] | None = None
        if self._connection:
            result = self._connection.close()
        self._connection = None
        self._config = None
        if result and result.is_fail:
            return AppResult.fail(result.error)
        return AppResult.success(Unit())

    def commit(self) -> AppResult[Unit]:
        if self.is_connected:
            result = self._connection.commit()
            if result.is_success:
                return AppResult.success(Unit())
            return AppResult.fail(result.error)
        return AppResult.fail("Connection failed")
    
    def rollback(self) -> AppResult[Unit]:
        if self.is_connected:
            result = self._connection.rollback()
            if result.is_success:
                return AppResult.success(Unit())
            return AppResult.fail(result.error)
        return AppResult.fail("Connection failed")

    def get_schemas(self) -> AppResult[list[str]]:
        if not self.is_connected:
            return AppResult.fail("Connection failed")
        schemas_result = self._connection.get_schemas()
        if schemas_result.is_success:
            return AppResult.success(schemas_result.value)
        return AppResult.fail(schemas_result.error)
    
    def schema_exists(self, schema_name: str) -> AppResult[bool]:
        if not self.is_connected:
            return AppResult.fail("Connection failed")
        schema_result = self._connection.schema_exists(schema_name)
        if schema_result.is_success:
            return AppResult.success(schema_result.value)
        return AppResult.fail(schema_result.error)

    def create_schema(self, schema_name: str) -> AppResult[Unit]:
        if not self.is_connected:
            return AppResult.fail("Connection failed")
        create_result = self._connection.create_schema(schema_name)
        if create_result.is_success:
            return AppResult.success(Unit())
        return AppResult.fail(create_result.error)

    def get_tables(self, schema_name: str) -> AppResult[list[str]]:
        if not self.is_connected:
            return AppResult.fail("Connection failed")
        tables_result = self._connection.get_tables(schema_name)
        if tables_result.is_success:
            return AppResult.success(tables_result.value)
        return AppResult.fail(tables_result.error)

    def get_table_columns(self, schema_name: str, table_name: str) -> AppResult[list[str]]:
        """Возвращает список колонок таблицы через information_schema."""
        query = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        result = self.execute_read_query(query, (schema_name, table_name))
        if result.is_fail:
            return AppResult.fail(result.error)

        try:
            columns = [row["column_name"] for row in result.value]
            return AppResult.success(columns)
        except Exception as exc:
            return AppResult.fail(f"Failed to parse columns list: {exc}")

    def execute_select_from_table(
        self,
        schema_name: str,
        table_name: str,
        columns: list[str],
        where_clause: str = "",
        params: tuple = (),
    ) -> AppResult[list[dict]]:
        """Выполняет безопасный SELECT по указанной таблице."""
        if not columns:
            return AppResult.fail("Columns list is empty")

        try:
            schema_sql = self._quote_identifier(schema_name)
            table_sql = self._quote_identifier(table_name)
            cols_sql = ", ".join(self._quote_identifier(col) for col in columns)
            query = f"SELECT {cols_sql} FROM {schema_sql}.{table_sql}"
            if where_clause:
                query = f"{query} {where_clause}"
            return self.execute_read_query(query, params)
        except Exception as exc:
            return AppResult.fail(f"Failed to build select query: {exc}")

    def execute_read_query(self, query: str, params: tuple = ()) -> AppResult[list[dict]]:
        """Выполняет произвольный read-only SQL запрос."""
        if not self.is_connected:
            return AppResult.fail("Connection failed")

        if not hasattr(self._connection, "execute_query"):
            return AppResult.fail("Active connection does not support read queries")

        result = self._connection.execute_query(query, params)
        if result.is_success:
            return AppResult.success(result.value)
        return AppResult.fail(result.error)

    def _quote_identifier(self, name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Identifier is empty")

        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            raise ValueError(f"Invalid SQL identifier: {name}")

        return f'"{name}"'

    def _get_document_repository(
        self,
        schema: str,
        table_name: str | None = None
    ) -> AppResult[IDocumentRepository]:
        if not self.is_connected:
            return AppResult.fail("Connection failed")
        
        if table_name:
            result = self._repository_factory.get_document_repository(self._connection, schema, table_name)
        else:
            result = self._repository_factory.get_document_repository(self._connection, schema)

        if result.is_success:
            return AppResult.success(result.value)
        else:
            return AppResult.fail(result.error)

    def _get_content_repository(
        self,
        schema: str,
        table_name: str | None = None
    ) -> AppResult[IContentRepository]:
        if not self.is_connected:
            return AppResult.fail("Connection failed")
        
        if table_name:
            result = self._repository_factory.get_content_repository(self._connection, schema, table_name)
        else:
            result = self._repository_factory.get_content_repository(self._connection, schema)

        if result.is_success:
            return AppResult.success(result.value)
        else:
            return AppResult.fail(result.error)

    def _get_layer_repository(
        self,
        schema: str,
        table_name: str | None = None
    ) -> AppResult[ILayerRepository]:
        if not self.is_connected:
            return AppResult.fail("Connection failed")
        
        if table_name:
            result = self._repository_factory.get_layer_repository(self._connection, schema, table_name)
        else:
            result = self._repository_factory.get_layer_repository(self._connection, schema)

        if result.is_success:
            return AppResult.success(result.value)
        else:
            return AppResult.fail(result.error)

    def _get_entity_repository(
        self,
        schema: str,
        table_name: str | None = None
    ) -> AppResult[IEntityRepository]:
        if not self.is_connected:
            return AppResult.fail("Connection failed")
        
        if table_name:
            result = self._repository_factory.get_entity_repository(self._connection, schema, table_name)
        else:
            result = self._repository_factory.get_entity_repository(self._connection, schema)
        
        if result.is_success:
            return AppResult.success(result.value)
        else:
            return AppResult.fail(result.error)
