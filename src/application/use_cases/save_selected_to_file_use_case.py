from __future__ import annotations

import os

import ezdxf

from ...application.interfaces import ILogger
from ...application.results import AppResult, Unit
from ...domain.repositories import IActiveDocumentRepository


class SaveSelectedToFileUseCase:
    """Вариант использования: сохранить выделенные сущности DXF в новый файл."""

    def __init__(self, active_repo: IActiveDocumentRepository, logger: ILogger):
        self._active_repo = active_repo
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

        try:
            drawing = ezdxf.readfile(source_doc.filepath)
            msp = drawing.modelspace()

            removed_count = self._filter_modelspace_entities(msp, selected_handles)

            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            drawing.saveas(output_path)

            report_lines.append(f"Entities removed: {removed_count}")
            report_lines.append(f"File saved: '{output_path}'")
            return AppResult.success(Unit()), "\n".join(report_lines)

        except Exception as exc:
            error_msg = f"Export failed: {str(exc)}"
            self._logger.error(error_msg)
            report_lines.append(f"ERROR: {error_msg}")
            return AppResult.fail(str(exc)), "\n".join(report_lines)

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

    def _filter_modelspace_entities(self, modelspace, selected_handles: set[str]) -> int:
        removed_count = 0
        for dxf_entity in list(modelspace):
            handle = str(getattr(dxf_entity.dxf, "handle", "")).strip().upper()
            if handle not in selected_handles:
                modelspace.delete_entity(dxf_entity)
                removed_count += 1
        return removed_count
