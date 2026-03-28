
import json
from uuid import UUID
from typing import List, Optional
from ....domain.value_objects import Result, Unit, DxfEntityType
from ....domain.entities import DXFEntity
from ....domain.repositories import IEntityRepository
from ....infrastructure.database.postgis import PostGISConnection, PostGISEntityConverter


class PostGISEntityRepository(IEntityRepository):
    
    def __init__(
        self,
        connection: PostGISConnection,
        schema: str,
        table_name: str
    ):
        self._connection = connection
        self._schema = schema
        self._table_name = table_name
        self._converter = PostGISEntityConverter()
        
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
        """Создание таблицы с сущностями"""
        create_table_query = f"""
            CREATE TABLE IF NOT EXISTS {self.full_name} (
                id UUID PRIMARY KEY,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                geometry GEOMETRY(GEOMETRYZ),
                attributes JSONB NOT NULL,
                geometries JSONB NOT NULL,
                extra_data JSONB NOT NULL
            )
        """
        try:
            self._connection.execute_query(create_table_query)
        except Exception as e:
            print(f"Error initializing table: {e}")

    def create(self, entity: DXFEntity) -> Result[DXFEntity]:
        try:
            query = f"""
                INSERT INTO {self.full_name} 
                (id, entity_type, name, geometry, attributes, geometries, extra_data)
                VALUES (%(id)s, %(entity_type)s, %(name)s, %(geometry)s, %(attributes)s, %(geometries)s, %(extra_data)s)
            """

            result = self._converter.to_db(entity)
            if not result.is_success:
                return result

            geometry, extra_data = result.value
            entity.add_extra_data(extra_data)

            data = {
                'id': entity.id,
                'entity_type': entity.entity_type.value,
                #'geometry': geometry,
                'geometry': None,
                'attributes': json.dumps(entity.attributes),
                'geometries': json.dumps(entity.geometries),
                'extra_data': json.dumps(entity.extra_data) 
            }
            
            self._connection.execute_query(query, data)
            return Result.success(entity)
            
        except Exception as e:
            return Result.fail(f"Failed to create content: {e}")
    
    def update(self, entity: DXFEntity) -> Result[DXFEntity]:
        try:
            query = f"""
                UPDATE {self.full_name} 
                SET entity_type = %(entity_type)s,
                    name = %(name)s,
                    geometry = %(geometry)s,
                    attributes = %(attributes)s,
                    geometries = %(geometries)s,
                    extra_data = %(extra_data)s
                WHERE id = %(id)s
            """

            result = self._converter.to_db(entity)
            if not result.is_success:
                return result

            geometry, extra_data = result.value
            entity.add_extra_data(extra_data)

            data = {
                'id': entity.id,
                'entity_type': entity.entity_type.value,
                'name': entity.name,
                #'geometry': geometry,
                'geometry': None,
                'attributes': json.dumps(entity.attributes),
                'geometries': json.dumps(entity.geometries),
                'extra_data': json.dumps(entity.extra_data)
            }
            
            self._connection.execute_query(query, data)
            return Result.success(entity)
            
        except Exception as e:
            return Result.fail(f"Failed to update entity: {e}")
    
    def remove(self, id: UUID) -> Result[Unit]:
        try:
            query = f"""
                DELETE FROM {self.full_name}
                WHERE id = %(id)s
            """
            self._connection.execute_query(query, {'id': id})
            return Result.success(Unit())
        except Exception as e:
            return Result.fail(f"Failed to remove layer: {e}")
    
    def get_by_id(self, id: UUID) -> Result[DXFEntity | None]:
        try:
            query = f"SELECT * FROM {self.full_name} WHERE id = %(id)s"
            result = self._connection.execute_query(query, {'id': str(id)})
            if result and len(result) > 0:
                entity = DXFEntity.create(
                    id=result[0]['id'],
                    entity_type=result[0]['entity_type'],
                    name=result[0]['name'],
                    attributes=json.loads(result[0]['attributes']),
                    geometries=json.loads(result[0]['geometries']),
                    extra_data=json.loads(result[0]['extra_data'])
                )
                return Result.success(entity)
            return Result.success(None)
        except Exception as e:
            return Result.fail(f"Failed to get entity: {e}")

    def get_by_name_and_type(self, name: str, type: DxfEntityType) -> Result[DXFEntity | None]:
        try:
            query = f"SELECT * FROM {self.full_name} WHERE name = %(name)s AND entity_type = %(entity_type)s"
            result = self._connection.execute_query(query, {'name': str(name), 'entity_type': type.value})
            if result and len(result) > 0:
                entity = DXFEntity.create(
                    id=result[0]['id'],
                    entity_type=result[0]['entity_type'],
                    name=result[0]['name'],
                    attributes=json.loads(result[0]['attributes']),
                    geometries=json.loads(result[0]['geometries']),
                    extra_data=json.loads(result[0]['extra_data'])
                )
                return Result.success(entity)
            return Result.success(None)
        except Exception as e:
            return Result.fail(f"Failed to get entity: {e}")

    def get_all(self) -> Result[List[DXFEntity]]:
        try:
            query = f"SELECT * FROM {self.full_name}"
            result = self._connection.execute_query(query)
            entities = []
            for row in result:
                entity = DXFEntity.create(
                    id=row['id'],
                    entity_type=row['entity_type'],
                    name=row['name'],
                    attributes=json.loads(row['attributes']),
                    geometries=json.loads(row['geometries']),
                    extra_data=json.loads(row['extra_data'])    
                )
                entities.append(entity)
            return Result.success(entities)
        except Exception as e:
            return Result.fail(f"Failed to get all entities: {e}")
    
