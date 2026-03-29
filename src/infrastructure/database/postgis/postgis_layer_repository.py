from __future__ import annotations

from uuid import UUID
from typing import List, Optional
from ....domain.value_objects import Result, Unit
from ....domain.entities import DXFLayer
from ....domain.repositories import ILayerRepository
from .postgis_connection import PostGISConnection


class PostGISLayerRepository(ILayerRepository):
    
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
                name TEXT NOT NULL,
                schema_name TEXT NOT NULL,
                table_name TEXT NOT NULL
            )
        """
        try:
            self._connection.execute_query(create_table_query)
        except Exception as e:
            print(f"Error initializing table: {e}")

    def create(self, entity: DXFLayer) -> Result[DXFLayer]:
        try:
            query = f"""
                INSERT INTO {self.full_name} 
                (id, document_id, name, schema_name, table_name)
                VALUES (%(id)s, %(document_id)s, %(name)s, %(schema_name)s, %(table_name)s)
            """

            data = {
                'id': str(entity.id),
                'document_id': str(entity.document_id),
                'name': entity.name,
                'schema_name': entity._schema_name,
                'table_name': entity.table_name
            }
            
            result = self._connection.execute_query(query, data)
            if result.is_fail:
                return Result.fail(f"Failed to create layer. {result.error}")
            return Result.success(entity)
            
        except Exception as e:
            return Result.fail(f"Failed to create content: {e}")
    
    def update(self, entity: DXFLayer) -> Result[DXFLayer]:
        try:
            query = f"""
                UPDATE {self.full_name} 
                SET document_id = %(document_id)s,
                    name = %(name)s,
                    schema_name = %(schema_name)s,
                    table_name = %(table_name)s
                WHERE id = %(id)s
            """

            data = {
                'id': str(entity.id),
                'document_id': str(entity.document_id),
                'name': entity.name,
                'schema_name': entity._schema_name,
                'table_name': entity.table_name
            }
            
            result = self._connection.execute_query(query, data)
            if result.is_fail:
                return Result.fail(f"Failed to update layer. {result.error}")
            return Result.success(entity)
            
        except Exception as e:
            return Result.fail(f"Failed to update layer: {e}")
    
    def remove(self, id: UUID) -> Result[Unit]:
        try:
            query = f"""
                DELETE FROM {self.full_name}
                WHERE id = %(id)s
            """
            result = self._connection.execute_query(query, {'id': str(id)})
            if result.is_fail:
                return Result.fail(f"Failed to remove layer. {result.error}")
            return Result.success(Unit())
        except Exception as e:
            return Result.fail(f"Failed to remove layer: {e}")
    
    def get_by_id(self, id: UUID) -> Result[Optional[DXFLayer]]:
        try:
            query = f"SELECT * FROM {self.full_name} WHERE id = %(id)s"
            result = self._connection.execute_query(query, {'id': str(id)})
            if result.is_fail:
                return Result.fail(f"Failed to get layer. {result.error}")
            rows = result.value
            if rows and len(rows) > 0:
                layer = DXFLayer.create(
                    document_id=rows[0]['document_id'],
                    name=rows[0]['name'],
                    schema_name=rows[0]['schema_name'],
                    table_name=rows[0]['table_name'],
                    id=rows[0]['id']
                )
                return Result.success(layer)
            return Result.fail(f"Layer with id {id} not found")
        except Exception as e:
            return Result.fail(f"Failed to get layer: {e}")

    def get_by_document_id_and_layer_name(self, document_id: UUID, layer_name: str) -> Result[DXFLayer | None]:
        try:
            query = f"SELECT * FROM {self.full_name} WHERE document_id = %(document_id)s AND name = %(name)s LIMIT 1"
            result = self._connection.execute_query(query, {'document_id': str(document_id), 'name': layer_name})
            if result.is_fail:
                return Result.fail(f"Failed to get layer by document ID and name. {result.error}")

            rows = result.value
            if rows and len(rows) > 0:
                row = rows[0]
                layer = DXFLayer.create(
                    document_id=row['document_id'],
                    name=row['name'],
                    schema_name=row['schema_name'],
                    table_name=row['table_name'],
                    id=row['id']
                )
                return Result.success(layer)

            return Result.fail(f"Layer '{layer_name}' not found for document '{document_id}'")
        except Exception as e:
            return Result.fail(f"Failed to get layers by document ID: {e}")

    def get_all_by_document_id(self, document_id: UUID) -> Result[List[DXFLayer]]:
        try:
            query = f"SELECT * FROM {self.full_name} WHERE document_id = %(document_id)s"
            result = self._connection.execute_query(query, {'document_id': str(document_id)})
            if result.is_fail:
                return Result.fail(f"Failed to get layers by document ID. {result.error}")
            layers = []
            for row in result.value:
                layer = DXFLayer.create(
                    document_id=row['document_id'],
                    name=row['name'],
                    schema_name=row['schema_name'],
                    table_name=row['table_name'],
                    id=row['id']
                )
                layers.append(layer)
            return Result.success(layers)
        except Exception as e:
            return Result.fail(f"Failed to get layers by document ID: {e}")
    
    def get_all(self) -> Result[List[DXFLayer]]:
        try:
            query = f"SELECT * FROM {self.full_name}"
            result = self._connection.execute_query(query)
            if result.is_fail:
                return Result.fail(f"Failed to get all layers. {result.error}")
            layers = []
            for row in result.value:
                layer = DXFLayer.create(
                    document_id=row['document_id'],
                    name=row['name'],
                    schema_name=row['schema_name'],
                    table_name=row['table_name'],
                    id=row['id']
                )
                layers.append(layer)
            return Result.success(layers)
        except Exception as e:
            return Result.fail(f"Failed to get all layers: {e}")
    
