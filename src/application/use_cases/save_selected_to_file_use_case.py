from __future__ import annotations

from ...application.interfaces import ILogger
from ...application.results import AppResult, Unit
from ...domain.repositories import IActiveDocumentRepository
from ...domain.services import IDXFWriter


class SaveSelectedToFileUseCase:
    """Вариант использования: сохранить выделенные сущности DXF в новый файл."""

    def __init__(
        self,
        active_repo: IActiveDocumentRepository,
        dxf_writer: IDXFWriter,
        logger: ILogger,
    ):
        self._active_repo = active_repo
        self._dxf_writer = dxf_writer
        self._logger = logger

    def execute(self, source_filename: str, output_path: str) -> tuple[AppResult[Unit], str]:
        """return (result, report)"""
        report_lines: list[str] = []
        report_lines.append("Starting selected entities export")

        if not source_filename:
            return AppResult.fail("Source filename is empty"), "\n".join(report_lines)

        if not output_path:
            return AppResult.fail("Output path is empty"), "\n".join(report_lines)

        doc_result = self._active_repo.get_by_filename(source_filename)
        if doc_result.is_fail or doc_result.value is None:
            error_msg = f"Source document '{source_filename}' not found"
            report_lines.append(f"ERROR: {error_msg}")
            return AppResult.fail(error_msg), "\n".join(report_lines)

        source_doc = doc_result.value
        if not source_doc.filepath:
            error_msg = f"Source file path for '{source_filename}' is empty"
            report_lines.append(f"ERROR: {error_msg}")
            return AppResult.fail(error_msg), "\n".join(report_lines)

        selected_handles = self._get_selected_handles(source_doc)

        if not selected_handles:
            error_msg = "No selected entities to export"
            report_lines.append(f"ERROR: {error_msg}")
            return AppResult.fail(error_msg), "\n".join(report_lines)

        report_lines.append(f"Selected entities: {len(selected_handles)}")

        save_result = self._dxf_writer.save_selected_by_handles(
            source_filepath=source_doc.filepath,
            output_path=output_path,
            selected_handles=selected_handles,
        )
        if save_result.is_success:
            removed_count = save_result.value
            report_lines.append(f"Entities removed: {removed_count}")
            report_lines.append(f"File saved: '{output_path}'")
            return AppResult.success(Unit()), "\n".join(report_lines)

        error_msg = f"Export failed: {save_result.error}"
        self._logger.error(error_msg)
        report_lines.append(f"ERROR: {error_msg}")
        return AppResult.fail(save_result.error), "\n".join(report_lines)

    def _get_selected_handles(self, source_doc) -> set[str]:
        selected_handles: set[str] = set()
        for layer in source_doc.layers.values():
            for entity in layer.entities.values():
                if not entity.is_selected:
                    continue
                handle = str(entity.attributes.get("handle", "")).strip().upper()
                if handle:
                    selected_handles.add(handle)
        return selected_handles
