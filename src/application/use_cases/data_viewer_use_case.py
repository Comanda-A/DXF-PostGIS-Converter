from __future__ import annotations

import inject

from ...application.database import DBSession
from ...application.dtos import ConnectionConfigDTO
from ...application.interfaces import ILogger
from ...application.results import AppResult


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
