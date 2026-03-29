from __future__ import annotations

from uuid import UUID
from typing import Optional
from ....domain.value_objects import Result, Unit
from ....domain.entities import DXFContent
from ....domain.repositories import IContentRepository
from .postgis_connection import PostGISConnection


class PostGISContentRepository(IContentRepository):
    
    def __init__(
        self,
        connection: PostGISConnection,
        schema: str,
        table_name: str
    ):
        self._connection = connection
        self._schema = schema
        self._table_name = table_name
        
        # Инициализация схемы и таблицы
        self._init_schema()
        self._init_table()

    @property  
    def full_name(self) -> str:
        """Полное имя таблицы со схемой"""
        return f"{self._schema}.{self._table_name}"
    
    def _init_schema(self):
        """Создание схемы если не существует"""
        result = self._connection.schema_exists(self._schema)
        if result.is_success and not result.value:
            self._connection.create_schema(self._schema)
    
    def _init_table(self):
        """Создание таблицы документов"""
        create_table_query = f"""
            CREATE TABLE IF NOT EXISTS {self.full_name} (
                id UUID PRIMARY KEY,
                document_id UUID NOT NULL,
                content BYTEA NOT NULL
            )
        """
        try:
            self._connection.execute_query(create_table_query)
        except Exception as e:
            print(f"Error initializing table: {e}")

    def create(self, entity: DXFContent) -> Result[DXFContent]:
        try:
            query = f"""
                INSERT INTO {self.full_name} 
                (id, document_id, content)
                VALUES (%(id)s, %(document_id)s, %(content)s)
            """

            data = {
                'id': str(entity.id),
                'document_id': str(entity.document_id),
                'content': entity.content
            }
            
            result = self._connection.execute_query(query, data)
            if result.is_fail:
                return Result.fail(f"Failed to create content. {result.error}")
            return Result.success(entity)
            
        except Exception as e:
            return Result.fail(f"Failed to create content: {e}")
    
    def update(self, entity: DXFContent) -> Result[DXFContent]:
        try:
            query = f"""
                UPDATE {self.full_name} 
                SET document_id = %(document_id)s,
                    content = %(content)s
                WHERE id = %(id)s
            """

            data = {
                'id': str(entity.id),
                'document_id': str(entity.document_id),
                'content': entity.content
            }
            
            result = self._connection.execute_query(query, data)
            if result.is_fail:
                return Result.fail(f"Failed to update content. {result.error}")
            return Result.success(entity)
            
        except Exception as e:
            return Result.fail(f"Failed to update content: {e}")
    
    def remove(self, id: UUID) -> Result[Unit]:
        try:
            query = f"""
                DELETE FROM {self.full_name}
                WHERE id = %(id)s
            """
            result = self._connection.execute_query(query, {'id': str(id)})
            if result.is_fail:
                return Result.fail(f"Failed to remove content. {result.error}")
            return Result.success(Unit())
        except Exception as e:
            return Result.fail(f"Failed to remove content: {e}")
    
    def get_by_id(self, id: UUID) -> Result[Optional[DXFContent]]:
        try:
            query = f"SELECT * FROM {self.full_name} WHERE id = %(id)s"
            result = self._connection.execute_query(query, {'id': str(id)})
            if result and len(result) > 0:
                content = DXFContent.create(
                    document_id=result[0]['document_id'],
                    content=result[0]['content'],
                    id=result[0]['id'],
                )
                return Result.success(content)
            return Result.success(None)
        except Exception as e:
            return Result.fail(f"Failed to get content: {e}")

    def get_by_document_id(self, document_id: UUID) -> Result[DXFContent | None]:
        try:
            query = f"SELECT * FROM {self.full_name} WHERE document_id = %(document_id)s"
            result = self._connection.execute_query(query, {'document_id': str(document_id)})
            
            # Проверяем результат выполнения запроса
            if result.is_fail:
                return Result.fail(f"Database query failed: {result.error}")
            
            # Получаем значение из Result
            rows = result.value
            
            if rows and len(rows) > 0:
                content = DXFContent.create(
                    document_id=rows[0]['document_id'],
                    content=rows[0]['content'],
                    id=rows[0]['id']
                )
                return Result.success(content)
            
            return Result.success(None)
            
        except Exception as e:
            return Result.fail(f"Failed to get content by document ID: {e}")
