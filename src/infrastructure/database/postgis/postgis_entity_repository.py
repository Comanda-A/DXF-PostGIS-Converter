from __future__ import annotations

import inject
import json
from uuid import UUID
from typing import List, Optional, Any
from ....domain.value_objects import Result, Unit, DxfEntityType
from ....domain.entities import DXFEntity
from ....domain.repositories import IEntityRepository
from ....application.interfaces import ILogger
from .postgis_connection import PostGISConnection
from .postgis_entity_converter import PostGISEntityConverter


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
        try:
            self._logger = inject.instance(ILogger)
        except:
            self._logger = None
        
        # Инициализация схемы и таблицы
        self._init_schema()
        self._init_table()

    @property  
    def full_name(self) -> str:
        """Полное имя таблицы со схемой с экранированием для PostgreSQL"""
        return f'"{self._schema}"."{self._table_name}"'
    
    def _init_schema(self):
        """Создание схемы если не существует"""
        result = self._connection.schema_exists(self._schema)
        if result.is_success and not result.value:
            schema_result = self._connection.create_schema(self._schema)
            if hasattr(schema_result, 'is_fail') and schema_result.is_fail:
                if self._logger:
                    self._logger.warning(f"Failed to create schema {self._schema}: {schema_result.error}")
    
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
            result = self._connection.execute_query(create_table_query)
            if hasattr(result, 'is_fail') and result.is_fail:
                # Откатываем транзакцию при ошибке инициализации таблицы
                self._connection.rollback()
                if self._logger:
                    self._logger.warning(f"Failed to initialize table {self.full_name}: {result.error}")
        except Exception as e:
            # Откатываем транзакцию при ошибке инициализации таблицы
            try:
                self._connection.rollback()
            except:
                pass
            if self._logger:
                self._logger.warning(f"Error initializing table {self.full_name}: {e}")
    
    def _make_serializable(self, obj: Any) -> Any:
        """Преобразует non-JSON-serializable объекты в совместимые типы"""
        if obj is None or isinstance(obj, (int, float, str, bool)):
            return obj
        
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        
        if isinstance(obj, (list, tuple)):
            return [self._make_serializable(v) for v in obj]
        
        # Для ezdxf Vec3, Vec2 и похожих объектов с координатами
        if hasattr(obj, 'x') and hasattr(obj, 'y'):
            if hasattr(obj, 'z'):
                return (float(obj.x), float(obj.y), float(obj.z))
            else:
                return (float(obj.x), float(obj.y))
        
        # Для других non-serializable объектов используем str()
        return str(obj)

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
                'id': str(entity.id),
                'entity_type': entity.entity_type.value,
                'name': entity.name,
                'geometry': geometry,
                'attributes': json.dumps(self._make_serializable(entity.attributes)),
                'geometries': json.dumps(self._make_serializable(entity.geometries)),
                'extra_data': json.dumps(self._make_serializable(entity.extra_data))
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
                'id': str(entity.id),
                'entity_type': entity.entity_type.value,
                'name': entity.name,
                'geometry': geometry,
                'attributes': json.dumps(self._make_serializable(entity.attributes)),
                'geometries': json.dumps(self._make_serializable(entity.geometries)),
                'extra_data': json.dumps(self._make_serializable(entity.extra_data))
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
            self._connection.execute_query(query, {'id': str(id)})
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
    
