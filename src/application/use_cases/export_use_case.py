from __future__ import annotations

import os
import tempfile

import inject

from ...application.database import DBSession
from ...application.dtos import ConnectionConfigDTO, ExportConfigDTO, ExportMode
from ...application.interfaces import ILogger
from ...application.results import AppResult, Unit
from ...domain.services import IDXFWriter


class ExportUseCase:
	"""Вариант использования: Экспортировать DXF из БД в файл."""

	def __init__(self, dxf_writer: IDXFWriter, logger: ILogger):
		self._dxf_writer = dxf_writer
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

				if config.export_mode == ExportMode.TABLES:
					content_result = self._read_table_entities(session, config.file_schema, config.filename)
					if content_result.is_fail:
						error_msg = f"Failed to reconstruct DXF content for '{config.filename}': {content_result.error}"
						report_lines.append(f"ERROR: {error_msg}")
						return AppResult.fail(error_msg), "\n".join(report_lines)

					content_bytes, reconstruction_report = content_result.value
					report_lines.append(reconstruction_report)
				else:
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

		if config.export_mode in (ExportMode.QGIS, ExportMode.TABLES):
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

	def _read_table_entities(
		self,
		session: DBSession,
		file_schema: str,
		filename: str,
	) -> AppResult[tuple[bytes, str]]:
		report_lines: list[str] = []
		report_lines.append(f"Reconstruction started for '{filename}' in schema '{file_schema}'")

		doc_repo_result = session._get_document_repository(file_schema)
		if doc_repo_result.is_fail:
			return AppResult.fail(doc_repo_result.error)

		doc_result = doc_repo_result.value.get_by_filename(filename)
		if doc_result.is_fail:
			return AppResult.fail(doc_result.error)

		doc = doc_result.value
		if doc is None:
			return AppResult.fail("Document not found")

		report_lines.append(f"Document found: id={doc.id}, filename='{doc.filename}'")

		layer_repo_result = session._get_layer_repository(file_schema)
		if layer_repo_result.is_fail:
			return AppResult.fail(layer_repo_result.error)

		layer_result = layer_repo_result.value.get_all_by_document_id(doc.id)
		if layer_result.is_fail:
			return AppResult.fail(layer_result.error)

		layers = layer_result.value
		if not layers:
			return AppResult.fail("No layers found to export")

		report_lines.append(f"Layers loaded: {len(layers)}")

		table_entities = []
		for layer in layers:
			report_lines.append(
				f"Layer '{layer.name}': schema='{layer.schema_name}', table='{layer.table_name}'"
			)
			entity_repo_result = session._get_entity_repository(layer.schema_name, layer.table_name)
			if entity_repo_result.is_fail:
				report_lines.append(
					f"Layer '{layer.name}': ERROR getting entity repository: {entity_repo_result.error}"
				)
				return AppResult.fail("\n".join(report_lines))

			entity_result = entity_repo_result.value.get_all()
			if entity_result.is_fail:
				report_lines.append(
					f"Layer '{layer.name}': ERROR loading entities: {entity_result.error}"
				)
				return AppResult.fail("\n".join(report_lines))

			entities = entity_result.value
			report_lines.append(f"Layer '{layer.name}': entities loaded={len(entities)}")
			table_entities.extend(entities)

		if not table_entities:
			report_lines.append("Reconstruction summary: reconstructed=0, skipped=0, by_type={}")
			return AppResult.fail("\n".join(report_lines))

		reconstruction_result = self._dxf_writer.reconstruct_from_entities(table_entities)
		if reconstruction_result.is_fail:
			report_lines.append(f"ERROR: {reconstruction_result.error}")
			return AppResult.fail("\n".join(report_lines))

		content_bytes, reconstruction_report = reconstruction_result.value
		report_lines.append(reconstruction_report)
		return AppResult.success((content_bytes, "\n".join(report_lines)))
