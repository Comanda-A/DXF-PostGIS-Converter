from __future__ import annotations

from collections.abc import Callable
from typing import Any

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QProgressDialog

from ..workers import LongTaskWorker


class ProgressTaskRunner:
    """Reusable helper to execute long tasks with modal progress dialog."""

    @staticmethod
    def run(
        parent,
        task: Callable[..., Any],
        *task_args,
        on_finished: Callable[[Any], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        progress_text: str = "progress",
        cancel_text: str = "cancel",
    ) -> LongTaskWorker:
        worker = LongTaskWorker(task, *task_args)

        progress_dialog = QProgressDialog(progress_text, cancel_text, 0, 0, parent)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(True)
        progress_dialog.setAutoReset(True)
        progress_dialog.repaint()

        def _on_finished(_task_id: int, result: Any) -> None:
            progress_dialog.close()
            if on_finished is not None:
                on_finished(result)

        def _on_error(error: str) -> None:
            progress_dialog.close()
            if on_error is not None:
                on_error(error)

        worker.finished.connect(_on_finished)
        worker.error.connect(_on_error)

        worker.start()
        progress_dialog.exec_()
        return worker
