from __future__ import annotations

import os
import tempfile
import inject

from ...application.database import DBSession
from ...application.dtos import ConnectionConfigDTO, ExportConfigDTO, ExportMode
from ...application.interfaces import ILogger
from ...application.results import AppResult, Unit


class ExportUseCase:
	"""Вариант использования: Экспортировать DXF из БД в файл."""

	def __init__(self, logger: ILogger):
		self._logger = logger

	def execute(
		self,
		connection: ConnectionConfigDTO,
		configs: list[ExportConfigDTO]
	) -> tuple[AppResult[Unit], str]:
		"""return (result, report)"""
		report_lines: list[str] = []
		report_lines.append("Starting DXF export process")

		if not connection:
			return AppResult.fail("No connection"), "\n".join(report_lines)

		if not configs:
			return AppResult.fail("No configs"), "\n".join(report_lines)

		report_lines.append(f"Export configurations loaded: {len(configs)} file(s) to process")

		session = inject.instance(DBSession)

		connect_result = session.connect(connection)
		if connect_result.is_fail:
			error_msg = f"Database connection failed: {connect_result.error}"
			report_lines.append(f"ERROR: {error_msg}")
			return AppResult.fail(connect_result.error), "\n".join(report_lines)

		report_lines.append("Successfully connected to database")

		try:
			for config in configs:
				if not config.filename:
					error_msg = "Export filename is empty"
					report_lines.append(f"ERROR: {error_msg}")
					return AppResult.fail(error_msg), "\n".join(report_lines)

				schema_result = session.schema_exists(config.file_schema)
				if schema_result.is_fail:
					error_msg = f"File schema check error: {schema_result.error}"
					report_lines.append(f"ERROR: {error_msg}")
					return AppResult.fail(error_msg), "\n".join(report_lines)

				if not schema_result.value:
					error_msg = f"File schema '{config.file_schema}' does not exist in database"
					report_lines.append(f"ERROR: {error_msg}")
					return AppResult.fail(error_msg), "\n".join(report_lines)

				report_lines.append(f"File schema verified: '{config.file_schema}'")

				report_lines.append(f"\n--- Processing file: {config.filename} ---")

				content_result = self._read_content(
					session=session,
					file_schema=config.file_schema,
					filename=config.filename,
				)

				if content_result.is_fail:
					error_msg = f"Failed to get content for '{config.filename}': {content_result.error}"
					report_lines.append(f"ERROR: {error_msg}")
					return AppResult.fail(error_msg), "\n".join(report_lines)

				content_bytes = content_result.value

				output_path = self._resolve_output_path(config)
				if not output_path:
					error_msg = "Output path is not defined"
					report_lines.append(f"ERROR: {error_msg}")
					return AppResult.fail(error_msg), "\n".join(report_lines)

				write_result = self._write_file(output_path, content_bytes)
				if write_result.is_fail:
					error_msg = f"Failed to write file '{output_path}': {write_result.error}"
					report_lines.append(f"ERROR: {error_msg}")
					return AppResult.fail(error_msg), "\n".join(report_lines)

				report_lines.append(f"File exported successfully: '{output_path}'")

			report_lines.append("\n" + "=" * 50)
			report_lines.append("EXPORT COMPLETED SUCCESSFULLY")
			report_lines.append(f"Total files processed: {len(configs)}")
			report_lines.append("=" * 50)

			return AppResult.success(Unit()), "\n".join(report_lines)

		except Exception as exc:
			error_msg = f"Export error: {str(exc)}"
			report_lines.append(f"ERROR: {error_msg}")
			self._logger.error(error_msg)

			if session.is_connected:
				session.rollback()

			return AppResult.fail(str(exc)), "\n".join(report_lines)

		finally:
			session.close()

	def _resolve_output_path(self, config: ExportConfigDTO) -> str | None:
		if config.output_path:
			return config.output_path

		if config.export_mode == ExportMode.QGIS:
			return os.path.join(tempfile.gettempdir(), config.filename)

		return None

	def _write_file(self, path: str, content: bytes) -> AppResult[Unit]:
		try:
			dir_name = os.path.dirname(path)
			if dir_name:
				os.makedirs(dir_name, exist_ok=True)

			with open(path, 'wb') as dxf_file:
				dxf_file.write(content)

			return AppResult.success(Unit())
		except Exception as exc:
			return AppResult.fail(str(exc))

	def _read_content(
		self,
		session: DBSession,
		file_schema: str,
		filename: str,
	) -> AppResult[bytes]:
		doc_repo_result = session._get_document_repository(file_schema)
		if doc_repo_result.is_fail:
			return AppResult.fail(doc_repo_result.error)

		doc_result = doc_repo_result.value.get_by_filename(filename)
		if doc_result.is_fail:
			return AppResult.fail(doc_result.error)

		document = doc_result.value
		if document is None:
			return AppResult.fail(f"Document '{filename}' not found in database")

		content_repo_result = session._get_content_repository(file_schema)
		if content_repo_result.is_fail:
			return AppResult.fail(content_repo_result.error)

		content_result = content_repo_result.value.get_by_document_id(document.id)
		if content_result.is_fail:
			return AppResult.fail(content_result.error)

		if content_result.value is None:
			return AppResult.fail(f"Content for '{filename}' not found in database")

		return AppResult.success(content_result.value.content)
