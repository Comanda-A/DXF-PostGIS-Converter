from __future__ import annotations

from typing import Dict, Type, Optional
from ...domain.value_objects import Result
from ...domain.repositories import (
    IConnection,
    IRepository,
    IRepositoryFactory,
    IDocumentRepository,
    IContentRepository,
    ILayerRepository,
    IEntityRepository
)


class RepositoryFactory(IRepositoryFactory):
    """Фабрика для создания репозиториев"""
    
    def __init__(self):
        # Ключ - тип соединения (класс), значение - класс репозитория
        self._document_repos: Dict[Type[IConnection], Type[IDocumentRepository]] = {}
        self._layer_repos: Dict[Type[IConnection], Type[ILayerRepository]] = {}
        self._entity_repos: Dict[Type[IConnection], Type[IEntityRepository]] = {}
        self._content_repos: Dict[Type[IConnection], Type[IContentRepository]] = {}
    
    def register_repositories(
        self, 
        connection_type: Type[IConnection], 
        document_repo_class: Optional[Type[IDocumentRepository]] = None,
        layer_repo_class: Optional[Type[ILayerRepository]] = None,
        entity_repo_class: Optional[Type[IEntityRepository]] = None,
        content_repo_class: Optional[Type[IContentRepository]] = None
    ) -> None:
        if document_repo_class:
            self._document_repos[connection_type] = document_repo_class
        if layer_repo_class:
            self._layer_repos[connection_type] = layer_repo_class
        if entity_repo_class:
            self._entity_repos[connection_type] = entity_repo_class
        if content_repo_class:
            self._content_repos[connection_type] = content_repo_class
    
    def _create_repository(
        self,
        connection: IConnection,
        repo_dict: Dict[Type[IConnection], Type[IRepository]],
        schema: str,
        table_name: str
    ) -> Result[IRepository]:
        """Общий метод для создания репозитория"""
        try:
            connection_type = type(connection)
            repo_class = repo_dict.get(connection_type)
            
            if not repo_class:
                return Result.fail(f"Repository class not registered for connection type {connection_type}")
            
            if not connection.is_connected:
                return Result.fail(f"Connection is not active for type {connection_type}")
            
            return Result.success(repo_class(
                connection=connection,
                schema=schema,
                table_name=table_name
            ))
        except Exception as e:
            return Result.fail(f"Failed to create repository: {e}")

    def _resolve_table_by_columns(
        self,
        connection: IConnection,
        schema: str,
        requested_table: str,
        required_columns: list[str],
        preferred_names: list[str] | None = None,
    ) -> str:
        """Возвращает совместимую таблицу в схеме по обязательным колонкам."""
        if not hasattr(connection, "execute_query"):
            return requested_table

        try:
            tables_result = connection.get_tables(schema)
            if tables_result.is_fail or not tables_result.value:
                return requested_table

            tables = tables_result.value

            candidates: list[str] = []
            if requested_table in tables:
                candidates.append(requested_table)

            for name in preferred_names or []:
                if name in tables and name not in candidates:
                    candidates.append(name)

            for name in tables:
                if name not in candidates:
                    candidates.append(name)

            required_set = set(required_columns)
            for table_name in candidates:
                columns_query = """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                """
                columns_result = connection.execute_query(columns_query, (schema, table_name))
                if columns_result.is_fail:
                    continue

                columns = {row.get("column_name") for row in columns_result.value}
                if required_set.issubset(columns):
                    return table_name

            return requested_table
        except Exception:
            return requested_table

    def get_document_repository(
        self,
        connection: IConnection,
        schema: str = "file_schema",
        table_name: str = "files"
    ) -> Result[IDocumentRepository]:
        """Создает репозиторий документов"""
        resolved_table = self._resolve_table_by_columns(
            connection=connection,
            schema=schema,
            requested_table=table_name,
            required_columns=["id", "filename"],
            preferred_names=["dxf_document", "dxf_documents", "documents", "dxf_files", "files"],
        )
        return self._create_repository(
            connection=connection,
            repo_dict=self._document_repos,
            schema=schema,
            table_name=resolved_table
        )
    
    def get_layer_repository(
        self,
        connection: IConnection,
        schema: str = "file_schema",
        table_name: str = "layers"
    ) -> Result[ILayerRepository]:
        """Создает репозиторий слоев"""
        return self._create_repository(
            connection=connection,
            repo_dict=self._layer_repos,
            schema=schema,
            table_name=table_name
        )
    
    def get_entity_repository(
        self,
        connection: IConnection,
        schema: str = "layer_schema",
        table_name: str = "layer_name"
    ) -> Result[IEntityRepository]:
        """Создает репозиторий сущностей"""
        return self._create_repository(
            connection=connection,
            repo_dict=self._entity_repos,
            schema=schema,
            table_name=table_name
        )
    
    def get_content_repository(
        self,
        connection: IConnection,
        schema: str = "file_schema",
        table_name: str = "content"
    ) -> Result[IContentRepository]:
        """Создает репозиторий контента"""
        return self._create_repository(
            connection=connection,
            repo_dict=self._content_repos,
            schema=schema,
            table_name=table_name
        )