
from typing import List, Optional
from uuid import UUID
from ....domain.entities import DXFDocument
from ....domain.repositories import IDocumentRepository
from ....domain.value_objects import Result, Unit
from ....infrastructure.database.postgis import PostGISConnection

class PostGISDocumentRepository(IDocumentRepository):
    """PostGIS репозиторий для документов"""
    
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
                filename TEXT NOT NULL UNIQUE,
                upload_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                update_date TIMESTAMP WITH TIME ZONE
            )
        """
        try:
            self._connection.execute_query(create_table_query)
        except Exception as e:
            print(f"Error initializing table: {e}")
    
    def create(self, entity: DXFDocument) -> Result[DXFDocument]:
        """Создание документа"""
        try:
            query = f"""
                INSERT INTO {self.full_name} 
                (id, filename, upload_date, update_date)
                VALUES (%(id)s, %(filename)s, %(upload_date)s, %(update_date)s)
            """

            data = {
                'id': entity.id,
                'filename': entity.filename,
                'upload_date': entity.upload_date,
                'update_date': entity.update_date
            }
            
            self._connection.execute_query(query, data)
            return Result.success(entity)
            
        except Exception as e:
            return Result.fail(f"Failed to create document: {e}")
    
    def update(self, entity: DXFDocument) -> Result[DXFDocument]:
        """Обновление документа по filename"""
        try:
            query = f"""
                UPDATE {self.full_name} 
                SET update_date = %(update_date)s
                WHERE filename = %(filename)s
            """

            data = {
                'update_date': entity.update_date,
                'filename': entity.filename
            }
            
            result = self._connection.execute_query(query, data)
            if result.is_fail:
                return Result.fail(f"Failed to update document: {result.error}")

            result = self.get_by_filename(entity.filename)
            if result.is_fail:
                return Result.fail(f"Failed get document: {result.error}")
            elif result.value is None:
                return Result.fail(f"Failed get document (not found)")

            return Result.success(result.value)
        except Exception as e:
            return Result.fail(f"Failed to update document: {e}")
    
    def remove(self, id: UUID) -> Result[Unit]:
        """Удаление документа по id"""
        try:
            query = f"DELETE FROM {self.full_name} WHERE id = %(id)s"
            self._connection.execute_query(query, {'id': str(id)})
            return Result.success(Unit())
        except Exception as e:
            return Result.fail(f"Failed to remove document: {e}")
    
    def get_by_id(self, id: UUID) -> Result[Optional[DXFDocument]]:
        """Получение документа по UUID"""
        try:
            query = f"SELECT * FROM {self.full_name} WHERE id = %(id)s"
            result = self._connection.execute_query(query, {'id': str(id)})
            if result.is_fail:
                return Result.fail(f"Failed to get document. {result.error}")
            data = result.value
            if data and len(data) > 0:
                doc = DXFDocument.create(
                    id=data[0]['id'],
                    filename=data[0]['filename'],
                    upload_date=data[0]['upload_date'],
                    update_date=data[0]['update_date']
                ) 
                return Result.success(doc)
            return Result.success(None)
        except Exception as e:
            return Result.fail(f"Failed to get document: {e}")
    
    def get_by_filename(self, filename: str) -> Result[DXFDocument | None]:
        """Получение документа по имени файла"""
        try:
            query = f"SELECT * FROM {self.full_name} WHERE filename = %(filename)s"
            result = self._connection.execute_query(query, {'filename': filename})
            if result.is_fail:
                return Result.fail(f"Failed to get document. {result.error}")
            data = result.value
            if data and len(data) > 0:
                doc = DXFDocument.create(
                    id=data[0]['id'],
                    filename=data[0]['filename'],
                    upload_date=data[0]['upload_date'],
                    update_date=data[0]['update_date']
                ) 
                return Result.success(doc)
            return Result.success(None)
        except Exception as e:
            return Result.fail(f"Failed to get document: {e}")
    
    def get_all(self) -> Result[list[DXFDocument]]:
        """Получение всех документов"""
        try:
            query = f"SELECT * FROM {self.full_name}"
            result = self._connection.execute_query(query)
            if result.is_fail:
                return Result.fail(f"Failed to get document. {result.error}")
            data = result.value
            if not data:
                return Result.success([])
            docs = [
                DXFDocument.create(
                    id=row['id'],
                    filename=row['filename'],
                    upload_date=row['upload_date'],
                    update_date=row['update_date']
                ) for row in data
            ]
            return Result.success(docs)
        except Exception as e:
            return Result.fail(f"Failed to get documents: {e}")
    
    def count(self) -> Result[int]:
        """Количество документов"""
        try:
            query = f"SELECT COUNT(*) as count FROM {self.full_name}"
            result = self._connection.execute_query(query)
            return Result.success(result[0]['count'] if result else 0)
        except Exception as e:
            return Result.fail(f"Failed to count documents: {e}")
    
    def exists(self, filename: str) -> Result[bool]:
        """Проверка существования документа"""
        try:
            query = f"SELECT EXISTS(SELECT 1 FROM {self.full_name} WHERE filename = %(filename)s) as exists_flag"
            result = self._connection.execute_query(query, {'filename': filename})
            
            # Проверяем, успешен ли результат
            if result.is_fail:
                return Result.fail(f"Failed to execute query: {result.error}")
            
            # Получаем значение из Result
            rows = result.value
            if rows and len(rows) > 0:
                # Используем явное имя колонки
                return Result.success(rows[0]['exists_flag'])
            else:
                return Result.success(False)
                
        except Exception as e:
            return Result.fail(f"Failed to check document existence: {e}")
