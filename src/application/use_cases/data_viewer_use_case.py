from __future__ import annotations

import inject
import os
import re
import tempfile

from ...application.database import DBSession
from ...application.dtos import ConnectionConfigDTO
from ...application.interfaces import ILogger
from ...application.results import AppResult
from ...domain.services import IDXFReader


class DataViewerUseCase:
	"""Вариант использования: чтение схем и DXF-файлов из БД."""

	def __init__(self, logger: ILogger):
		self._logger = logger

	def get_schemas(self, connection: ConnectionConfigDTO) -> AppResult[list[str]]:
		"""Возвращает список схем для выбранного подключения."""
		if not connection:
			return AppResult.fail("No connection")

		session = inject.instance(DBSession)

		try:
			connect_result = session.connect(connection)
			if connect_result.is_fail:
				return AppResult.fail(connect_result.error)

			schemas_result = session.get_schemas()
			if schemas_result.is_fail:
				return AppResult.fail(schemas_result.error)

			return AppResult.success(sorted(schemas_result.value))
		except Exception as exc:
			self._logger.error(f"Failed to load schemas: {exc}")
			return AppResult.fail(str(exc))
		finally:
			session.close()

	def get_filenames(
		self,
		connection: ConnectionConfigDTO,
		file_schema: str,
	) -> AppResult[list[str]]:
		"""Возвращает список имен DXF-файлов из схемы хранения файлов."""
		if not connection:
			return AppResult.fail("No connection")

		if not file_schema:
			return AppResult.fail("No file schema")

		session = inject.instance(DBSession)

		try:
			connect_result = session.connect(connection)
			if connect_result.is_fail:
				return AppResult.fail(connect_result.error)

			schema_result = session.schema_exists(file_schema)
			if schema_result.is_fail:
				return AppResult.fail(schema_result.error)

			if not schema_result.value:
				return AppResult.success([])

			doc_repo_result = session._get_document_repository(file_schema)
			if doc_repo_result.is_fail:
				return AppResult.fail(doc_repo_result.error)

			docs_result = doc_repo_result.value.get_all()
			if docs_result.is_fail:
				return AppResult.fail(docs_result.error)

			filenames = sorted([doc.filename for doc in docs_result.value])
			return AppResult.success(filenames)
		except Exception as exc:
			self._logger.error(f"Failed to load filenames from '{file_schema}': {exc}")
			return AppResult.fail(str(exc))
		finally:
			session.close()

	def get_documents(
		self,
		connection: ConnectionConfigDTO,
		file_schema: str,
	) -> AppResult[list[dict]]:
		"""Возвращает документы с базовой мета-информацией для UI экспорта."""
		if not connection:
			return AppResult.fail("No connection")

		if not file_schema:
			return AppResult.fail("No file schema")

		session = inject.instance(DBSession)

		try:
			connect_result = session.connect(connection)
			if connect_result.is_fail:
				return AppResult.fail(connect_result.error)

			schema_result = session.schema_exists(file_schema)
			if schema_result.is_fail:
				return AppResult.fail(schema_result.error)

			if not schema_result.value:
				return AppResult.success([])

			doc_repo_result = session._get_document_repository(file_schema)
			if doc_repo_result.is_fail:
				return AppResult.fail(doc_repo_result.error)

			docs_result = doc_repo_result.value.get_all()
			if docs_result.is_fail:
				return AppResult.fail(docs_result.error)

			documents = sorted(
				[
					{
						"id": doc.id,
						"filename": doc.filename,
						"upload_date": doc.upload_date,
						"update_date": doc.update_date,
					}
					for doc in docs_result.value
				],
				key=lambda d: d["filename"],
			)
			return AppResult.success(documents)
		except Exception as exc:
			self._logger.error(f"Failed to load document metadata from '{file_schema}': {exc}")
			return AppResult.fail(str(exc))
		finally:
			session.close()

	def delete_document_by_filename(
		self,
		connection: ConnectionConfigDTO,
		file_schema: str,
		filename: str,
	) -> AppResult[bool]:
		"""Удаляет документ и связанные записи контента/слоёв из схемы хранения."""
		if not connection:
			return AppResult.fail("No connection")

		if not file_schema:
			return AppResult.fail("No file schema")

		if not filename:
			return AppResult.fail("No filename")

		session = inject.instance(DBSession)

		try:
			connect_result = session.connect(connection)
			if connect_result.is_fail:
				return AppResult.fail(connect_result.error)

			doc_repo_result = session._get_document_repository(file_schema)
			if doc_repo_result.is_fail:
				return AppResult.fail(doc_repo_result.error)
			doc_repo = doc_repo_result.value

			doc_result = doc_repo.get_by_filename(filename)
			if doc_result.is_fail:
				return AppResult.fail(doc_result.error)

			doc = doc_result.value
			if doc is None:
				return AppResult.success(False)

			content_repo_result = session._get_content_repository(file_schema)
			if content_repo_result.is_success:
				content_result = content_repo_result.value.get_by_document_id(doc.id)
				if content_result.is_success and content_result.value is not None:
					remove_content_result = content_repo_result.value.remove(content_result.value.id)
					if remove_content_result.is_fail:
						return AppResult.fail(remove_content_result.error)

			layer_repo_result = session._get_layer_repository(file_schema)
			if layer_repo_result.is_success:
				layers_result = layer_repo_result.value.get_all_by_document_id(doc.id)
				if layers_result.is_success:
					for layer in layers_result.value:
						remove_layer_result = layer_repo_result.value.remove(layer.id)
						if remove_layer_result.is_fail:
							return AppResult.fail(remove_layer_result.error)

			remove_doc_result = doc_repo.remove(doc.id)
			if remove_doc_result.is_fail:
				return AppResult.fail(remove_doc_result.error)

			commit_result = session.commit()
			if commit_result.is_fail:
				return AppResult.fail(commit_result.error)

			return AppResult.success(True)
		except Exception as exc:
			session.rollback()
			self._logger.error(f"Failed to delete document '{filename}' from '{file_schema}': {exc}")
			return AppResult.fail(str(exc))
		finally:
			session.close()

	def get_document_info(
		self,
		connection: ConnectionConfigDTO,
		file_schema: str,
		filename: str,
	) -> AppResult[dict]:
		"""Возвращает расширенную информацию о документе для карточки UI."""
		if not connection:
			return AppResult.fail("No connection")

		if not file_schema:
			return AppResult.fail("No file schema")

		if not filename:
			return AppResult.fail("No filename")

		session = inject.instance(DBSession)

		try:
			connect_result = session.connect(connection)
			if connect_result.is_fail:
				return AppResult.fail(connect_result.error)

			doc_repo_result = session._get_document_repository(file_schema)
			if doc_repo_result.is_fail:
				return AppResult.fail(doc_repo_result.error)
			doc_repo = doc_repo_result.value

			doc_result = doc_repo.get_by_filename(filename)
			if doc_result.is_fail:
				return AppResult.fail(doc_result.error)
			doc = doc_result.value
			if doc is None:
				return AppResult.fail("Document not found")

			file_size = 0
			content_repo_result = session._get_content_repository(file_schema)
			if content_repo_result.is_success:
				content_repo = content_repo_result.value
				content_schema = getattr(content_repo, "_schema", file_schema)
				content_table = getattr(content_repo, "_table_name", "content")

				columns_result = session.get_table_columns(content_schema, content_table)
				if columns_result.is_success:
					columns = set(columns_result.value)
					schema_sql = self._quote_identifier(content_schema)
					table_sql = self._quote_identifier(content_table)

					if {"document_id", "content"}.issubset(columns):
						size_query = (
							f"SELECT OCTET_LENGTH(content) AS size_bytes "
							f"FROM {schema_sql}.{table_sql} "
							f"WHERE document_id = %s LIMIT 1"
						)
						size_result = session.execute_read_query(size_query, (str(doc.id),))
						if size_result.is_success and size_result.value:
							file_size = int(size_result.value[0].get("size_bytes") or 0)

					elif {"id", "file_content"}.issubset(columns):
						size_query = (
							f"SELECT OCTET_LENGTH(file_content) AS size_bytes "
							f"FROM {schema_sql}.{table_sql} "
							f"WHERE id = %s LIMIT 1"
						)
						size_result = session.execute_read_query(size_query, (str(doc.id),))
						if size_result.is_success and size_result.value:
							file_size = int(size_result.value[0].get("size_bytes") or 0)

			layer_count = 0
			layer_repo_result = session._get_layer_repository(file_schema)
			if layer_repo_result.is_success:
				layers_result = layer_repo_result.value.get_all_by_document_id(doc.id)
				if layers_result.is_success:
					layer_count = len(layers_result.value)

			return AppResult.success(
				{
					"id": doc.id,
					"filename": doc.filename,
					"upload_date": doc.upload_date,
					"update_date": doc.update_date,
					"file_size": file_size,
					"layer_count": layer_count,
				}
			)
		except Exception as exc:
			self._logger.error(f"Failed to load document info for '{filename}' from '{file_schema}': {exc}")
			return AppResult.fail(str(exc))
		finally:
			session.close()

	def _quote_identifier(self, identifier: str) -> str:
		if not identifier or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", identifier):
			raise ValueError(f"Invalid SQL identifier: {identifier}")
		return f'"{identifier}"'

	def generate_preview_by_filename(
		self,
		connection: ConnectionConfigDTO,
		file_schema: str,
		filename: str,
		output_dir: str,
	) -> AppResult[str]:
		"""Генерирует SVG-превью из DXF-контента в БД для указанного файла."""
		if not connection:
			return AppResult.fail("No connection")
		if not file_schema:
			return AppResult.fail("No file schema")
		if not filename:
			return AppResult.fail("No filename")
		if not output_dir:
			return AppResult.fail("No output directory")

		session = inject.instance(DBSession)
		dxf_reader = inject.instance(IDXFReader)

		temp_path = ""
		try:
			connect_result = session.connect(connection)
			if connect_result.is_fail:
				return AppResult.fail(connect_result.error)

			doc_repo_result = session._get_document_repository(file_schema)
			if doc_repo_result.is_fail:
				return AppResult.fail(doc_repo_result.error)
			doc_result = doc_repo_result.value.get_by_filename(filename)
			if doc_result.is_fail:
				return AppResult.fail(doc_result.error)
			doc = doc_result.value
			if doc is None:
				return AppResult.fail("Document not found")

			content_repo_result = session._get_content_repository(file_schema)
			if content_repo_result.is_fail:
				return AppResult.fail(content_repo_result.error)

			content_result = content_repo_result.value.get_by_document_id(doc.id)
			if content_result.is_fail:
				return AppResult.fail(content_result.error)
			if content_result.value is None or not content_result.value.content:
				return AppResult.fail("Document content is empty")

			fd, temp_path = tempfile.mkstemp(suffix=".dxf")
			os.close(fd)
			with open(temp_path, "wb") as temp_file:
				temp_file.write(content_result.value.content)

			preview_result = dxf_reader.save_svg_preview(
				filepath=temp_path,
				output_dir=output_dir,
				filename=filename,
			)
			if preview_result.is_fail:
				return AppResult.fail(preview_result.error)

			return AppResult.success(preview_result.value)
		except Exception as exc:
			self._logger.error(f"Failed to generate preview for '{filename}': {exc}")
			return AppResult.fail(str(exc))
		finally:
			if temp_path and os.path.exists(temp_path):
				os.remove(temp_path)
			session.close()
