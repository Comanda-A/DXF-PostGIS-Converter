from __future__ import annotations

from qgis.PyQt.QtWidgets import QMessageBox, QProgressDialog
from qgis.PyQt.QtCore import Qt
from qgis.core import Qgis

from ...application.results import AppResult
from ...application.use_cases import SelectAreaUseCase
from ...domain.value_objects import AreaSelectionParams, SelectionMode, SelectionRule, ShapeType
from ...presentation.workers import LongTaskWorker


class AreaSelectionController:
    """Оркестрация выбора сущностей по области для ConverterDialog."""

    def __init__(self, dialog, iface, localization, select_area_use_case: SelectAreaUseCase):
        self._dialog = dialog
        self._iface = iface
        self._localization = localization
        self._select_area_use_case = select_area_use_case
        self._worker: LongTaskWorker | None = None
        self._active_map_tool = None
        self._progress_dialog: QProgressDialog | None = None

    def _title(self) -> str:
        return self._localization.tr("MAIN_DIALOG", "dialog_title")

    def _hint(self) -> str:
        return self._localization.tr("MAIN_DIALOG", "coord_edit")

    def _current_filename(self) -> str:
        return self._dialog.file_filter_combo.currentText().strip()

    def start_map_selection(self):
        filename = self._current_filename()
        if not filename:
            self._dialog._logger.warning("Area selection start aborted: no active file")
            self._iface.messageBar().pushMessage(
                self._title(),
                self._hint(),
                level=Qgis.Warning,
                duration=4,
            )
            return

        from ...draw.DrawRect import RectangleMapTool
        from ...draw.DrawCircle import CircleMapTool
        from ...draw.DrawPolygon import PolygonMapTool

        shape_index = self._dialog.type_shape.currentIndex()
        tool_by_shape = {
            0: RectangleMapTool,
            1: CircleMapTool,
            2: PolygonMapTool,
        }
        tool_cls = tool_by_shape.get(shape_index)
        if tool_cls is None:
            self._dialog._logger.warning(f"Area selection start aborted: unsupported shape index {shape_index}")
            return

        # Keep a strong reference or QGIS can drop the active map tool.
        self._active_map_tool = tool_cls(self._iface.mapCanvas(), self._dialog)
        self._dialog._logger.message(
            f"Area selection tool activated: file='{filename}', shape_index={shape_index}, tool={tool_cls.__name__}"
        )
        self._dialog.hide()
        self._iface.mapCanvas().setMapTool(self._active_map_tool)
        self._iface.messageBar().pushMessage(
            self._title(),
            self._hint(),
            level=Qgis.Info,
            duration=5,
        )

    def select_async(self, *shape_args):
        filename = self._current_filename()
        if not filename:
            self._dialog._logger.warning("Area selection execution aborted: no active file")
            QMessageBox.warning(self._dialog, self._title(), self._hint())
            return

        params = AreaSelectionParams(
            shape_type={
                0: ShapeType.RECTANGLE,
                1: ShapeType.CIRCLE,
                2: ShapeType.POLYGON,
            }.get(self._dialog.type_shape.currentIndex(), ShapeType.RECTANGLE),
            selection_rule={
                0: SelectionRule.INSIDE,
                1: SelectionRule.OUTSIDE,
                2: SelectionRule.INTERSECT,
            }.get(self._dialog.type_selection.currentIndex(), SelectionRule.INSIDE),
            selection_mode={
                0: SelectionMode.JOIN,
                1: SelectionMode.REPLACE,
                2: SelectionMode.SUBTRACT,
            }.get(self._dialog.selection_mode.currentIndex(), SelectionMode.JOIN),
            shape_args=shape_args,
        )

        self._dialog._logger.message(
            f"Area selection execute: file='{filename}', shape={params.shape_type.value}, "
            f"rule={params.selection_rule.value}, mode={params.selection_mode.value}, "
            f"args_count={len(params.shape_args)}"
        )

        self._show_progress()

        self._worker = LongTaskWorker(self._execute_selection, filename, params)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _execute_selection(self, filename: str, params: AreaSelectionParams):
        return self._select_area_use_case.execute(filename, params)

    def _on_finished(self, task_id: int, result):
        if isinstance(result, AppResult) and result.is_fail:
            self._dialog._logger.warning(f"Area selection failed: {result.error}")
            QMessageBox.warning(
                self._dialog,
                self._title(),
                result.error,
            )
        elif isinstance(result, AppResult):
            self._dialog._logger.message("Area selection finished: refreshing documents view")
            self._dialog.refresh_documents_view()
            self._dialog._logger.message("Documents view refreshed after area selection")

        self._cleanup_ui_state()

    def _on_error(self, error_message: str):
        self._dialog._logger.error(f"Area selection worker error: {error_message}")
        QMessageBox.critical(
            self._dialog,
            self._title(),
            error_message,
        )
        self._cleanup_ui_state()

    def _show_progress(self):
        if self._progress_dialog:
            self._progress_dialog.close()

        self._progress_dialog = QProgressDialog(self._hint(), "", 0, 0, self._dialog)
        self._progress_dialog.setWindowModality(Qt.WindowModal)
        self._progress_dialog.setCancelButton(None)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setAutoClose(True)
        self._progress_dialog.setAutoReset(True)
        self._progress_dialog.show()

    def _cleanup_ui_state(self):
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog.deleteLater()
            self._progress_dialog = None

        self._dialog._show_window()
        self._active_map_tool = None
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
