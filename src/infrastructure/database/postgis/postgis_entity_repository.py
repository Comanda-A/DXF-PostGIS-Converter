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
                name TEXT NOT NULL,
                geometry GEOMETRY(GEOMETRYZ),
                data JSONB NOT NULL
            )
        """
        try:
            result = self._connection.execute_query(create_table_query)
            if hasattr(result, 'is_fail') and result.is_fail:
                # Откатываем транзакцию при ошибке инициализации таблицы
                self._connection.rollback()
                if self._logger:
                    self._logger.warning(f"Failed to initialize table {self.full_name}: {result.error}")
                return

            self._migrate_table_structure()
        except Exception as e:
            # Откатываем транзакцию при ошибке инициализации таблицы
            try:
                self._connection.rollback()
            except:
                pass
            if self._logger:
                self._logger.warning(f"Error initializing table {self.full_name}: {e}")

    def _migrate_table_structure(self) -> None:
        """
        Приводит таблицу сущностей к актуальной схеме:
        id, name, geometry, data(JSONB).

        Миграция поддерживает legacy-структуру с отдельными columns
        entity_type/attributes/geometries/extra_data и промежуточную структуру
        без id.
        """
        try:
            columns_query = """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %(schema)s AND table_name = %(table)s
            """
            columns_result = self._connection.execute_query(columns_query, {
                'schema': self._schema,
                'table': self._table_name,
            })
            if columns_result.is_fail:
                if self._logger:
                    self._logger.warning(f"Failed to inspect columns for {self.full_name}: {columns_result.error}")
                return

            columns = {row['column_name'] for row in (columns_result.value or [])}

            if 'id' not in columns:
                self._connection.execute_query(f"ALTER TABLE {self.full_name} ADD COLUMN id UUID")
                columns.add('id')

            if 'name' not in columns:
                self._connection.execute_query(f"ALTER TABLE {self.full_name} ADD COLUMN name TEXT")
                columns.add('name')

            if 'geometry' not in columns:
                self._connection.execute_query(f"ALTER TABLE {self.full_name} ADD COLUMN geometry GEOMETRY(GEOMETRYZ)")
                columns.add('geometry')

            if 'data' not in columns:
                self._connection.execute_query(f"ALTER TABLE {self.full_name} ADD COLUMN data JSONB")
                columns.add('data')

            legacy_cols = {'entity_type', 'attributes', 'geometries', 'extra_data'}
            if legacy_cols.intersection(columns):
                migrate_legacy_query = f"""
                    UPDATE {self.full_name}
                    SET data = jsonb_build_object(
                        'entity_type', COALESCE(entity_type, 'UNKNOWN'),
                        'attributes', COALESCE(attributes, '{{}}'::jsonb),
                        'geometries', COALESCE(geometries, '{{}}'::jsonb),
                        'extra_data', COALESCE(extra_data, '{{}}'::jsonb)
                    )
                    WHERE data IS NULL OR data = '{{}}'::jsonb
                """
                self._connection.execute_query(migrate_legacy_query)

            self._connection.execute_query(f"UPDATE {self.full_name} SET data = '{{}}'::jsonb WHERE data IS NULL")

            self._connection.execute_query("CREATE EXTENSION IF NOT EXISTS pgcrypto")

            fill_id_query = f"""
                UPDATE {self.full_name}
                SET id = CASE
                    WHEN data ? 'id' AND (data->>'id') ~* '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[1-5][0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$'
                        THEN (data->>'id')::uuid
                    ELSE gen_random_uuid()
                END
                WHERE id IS NULL
            """
            self._connection.execute_query(fill_id_query)

            # DRY: keep single source for id in dedicated column.
            self._connection.execute_query(f"UPDATE {self.full_name} SET data = data - 'id' WHERE data ? 'id'")

            # Ensure id uniqueness before adding PK.
            deduplicate_query = f"""
                DELETE FROM {self.full_name} a
                USING {self.full_name} b
                WHERE a.ctid < b.ctid AND a.id = b.id
            """
            self._connection.execute_query(deduplicate_query)

            pk_check_query = """
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE c.contype = 'p'
                  AND n.nspname = %(schema)s
                  AND t.relname = %(table)s
                LIMIT 1
            """
            pk_check_result = self._connection.execute_query(pk_check_query, {
                'schema': self._schema,
                'table': self._table_name,
            })
            has_pk = pk_check_result.is_success and bool(pk_check_result.value)
            if not has_pk:
                self._connection.execute_query(f"ALTER TABLE {self.full_name} ADD PRIMARY KEY (id)")

            for legacy_col in ('entity_type', 'attributes', 'geometries', 'extra_data'):
                if legacy_col in columns:
                    self._connection.execute_query(f"ALTER TABLE {self.full_name} DROP COLUMN IF EXISTS {legacy_col}")

            self._connection.commit()
        except Exception as exc:
            try:
                self._connection.rollback()
            except Exception:
                pass
            if self._logger:
                self._logger.warning(f"Failed to migrate entity table structure for {self.full_name}: {exc}")
    
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
                (id, name, geometry, data)
                VALUES (%(id)s, %(name)s, %(geometry)s, %(data)s)
                ON CONFLICT (id)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    geometry = EXCLUDED.geometry,
                    data = EXCLUDED.data
            """

            result = self._converter.to_db(entity)
            if not result.is_success:
                return result

            geometry, converter_extra_data  = result.value

            # TODO: При импорте сохраняется мусор PostGIS конвертера в extra_data сущности.
            # Нужно во время экспорта его убирать, иначе этот мусор будет висеть и в случае импорта в другие СУБД попадет в них.
            for key, value in converter_extra_data.items():
                if key not in entity.extra_data:
                    entity.add_extra_data({key: value})

            payload = {
                'entity_type': entity.entity_type.value,
                'attributes': self._make_serializable(entity.attributes),
                'geometries': self._make_serializable(entity.geometries),
                'extra_data': self._make_serializable(entity.extra_data),
            }

            data = {
                'id': str(entity.id),
                'name': entity.name,
                'geometry': geometry,
                'data': json.dumps(payload)
            }
            
            self._connection.execute_query(query, data)
            return Result.success(entity)
            
        except Exception as e:
            return Result.fail(f"Failed to create content: {e}")
    
    def update(self, entity: DXFEntity) -> Result[DXFEntity]:
        try:
            query = f"""
                UPDATE {self.full_name} 
                SET name = %(name)s,
                    geometry = %(geometry)s,
                    data = %(data)s
                WHERE id = %(id)s::uuid
            """

            result = self._converter.to_db(entity)
            if not result.is_success:
                return result

            geometry, converter_extra_data  = result.value

            # TODO: При импорте сохраняется мусор PostGIS конвертера в extra_data сущности.
            # Нужно во время экспорта его убирать, иначе этот мусор будет висеть и в случае импорта в другие СУБД попадет в них.
            for key, value in converter_extra_data.items():
                if key not in entity.extra_data:
                    entity.add_extra_data({key: value})
            
            payload = {
                'entity_type': entity.entity_type.value,
                'attributes': self._make_serializable(entity.attributes),
                'geometries': self._make_serializable(entity.geometries),
                'extra_data': self._make_serializable(entity.extra_data),
            }

            data = {
                'id': str(entity.id),
                'name': entity.name,
                'geometry': geometry,
                'data': json.dumps(payload)
            }
            
            self._connection.execute_query(query, data)
            return Result.success(entity)
            
        except Exception as e:
            return Result.fail(f"Failed to update entity: {e}")
    
    def remove(self, id: UUID) -> Result[Unit]:
        try:
            query = f"""
                DELETE FROM {self.full_name}
                WHERE id = %(id)s::uuid
            """
            self._connection.execute_query(query, {'id': str(id)})
            return Result.success(Unit())
        except Exception as e:
            return Result.fail(f"Failed to remove layer: {e}")
    
    def get_by_id(self, id: UUID) -> Result[DXFEntity | None]:
        try:
            query = f"SELECT * FROM {self.full_name} WHERE id = %(id)s::uuid"
            result = self._connection.execute_query(query, {'id': str(id)}).value
            if result and len(result) > 0:
                row = result[0]
                payload = row['data'] if isinstance(row['data'], dict) else json.loads(row['data'])
                entity = DXFEntity.create(
                    id=row['id'],
                    entity_type=payload.get('entity_type'),
                    name=row['name'],
                    attributes=payload.get('attributes', {}),
                    geometries=payload.get('geometries', {}),
                    extra_data=payload.get('extra_data', {})
                )
                return Result.success(entity)
            return Result.success(None)
        except Exception as e:
            return Result.fail(f"Failed to get entity: {e}")

    def get_by_name_and_type(self, name: str, type: DxfEntityType) -> Result[DXFEntity | None]:
        try:
            query = f"SELECT * FROM {self.full_name} WHERE name = %(name)s AND data->>'entity_type' = %(entity_type)s"
            result = self._connection.execute_query(query, {'name': str(name), 'entity_type': type.value}).value
            
            if result and len(result) > 0:
                row = result[0]
                payload = row['data'] if isinstance(row['data'], dict) else json.loads(row['data'])
                
                entity = DXFEntity.create(
                    id=row['id'],
                    entity_type=payload.get('entity_type'),
                    name=row['name'],
                    attributes=payload.get('attributes', {}),
                    geometries=payload.get('geometries', {}),
                    extra_data=payload.get('extra_data', {})
                )
                return Result.success(entity)
            
            return Result.success(None)
        except Exception as e:
            return Result.fail(f"Failed to get entity: {e}")

    def get_all(self) -> Result[List[DXFEntity]]:
        try:
            query = f"SELECT * FROM {self.full_name}"
            result = self._connection.execute_query(query).value
            entities = []
            for row in result:
                payload = row['data'] if isinstance(row['data'], dict) else json.loads(row['data'])
                
                entity = DXFEntity.create(
                    id=row['id'],
                    entity_type=payload.get('entity_type'),
                    name=row['name'],
                    attributes=payload.get('attributes', {}),
                    geometries=payload.get('geometries', {}),
                    extra_data=payload.get('extra_data', {})
                )
                entities.append(entity)
            return Result.success(entities)
        except Exception as e:
            return Result.fail(f"Failed to get all entities: {e}")
    
    def delete_all(self) -> Result[Unit]:
        """Удалить все сущности из таблицы"""
        try:
            query = f"DELETE FROM {self.full_name}"
            self._connection.execute_query(query)
            return Result.success(Unit())
        except Exception as e:
            return Result.fail(f"Failed to delete all entities from {self.full_name}: {e}")
    
