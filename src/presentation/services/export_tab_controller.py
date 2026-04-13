from __future__ import annotations

import os
import tempfile
from functools import partial
from datetime import datetime
from pathlib import Path
from time import perf_counter

from PyQt5.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import (
    QMessageBox,
    QTreeWidgetItem,
    QDialog,
    QFileDialog,
    QProgressDialog,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
)
from PyQt5.QtCore import Qt, QSignalBlocker
from PyQt5.QtCore import QTimer

from ...application.dtos import ConnectionConfigDTO, ExportConfigDTO, ExportMode
from ...application.interfaces import ILocalization, ILogger
from ...application.services import ConnectionConfigService
from ...application.use_cases import DataViewerUseCase, ExportUseCase
from ...presentation.workers import LongTaskWorker
from ...presentation.widgets import SvgPreviewDialog


class _PreviewButton(QPushButton):
    """Clickable preview button that shows magnifier hint on hover."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._placeholder_text = "N/A"
        self._hovered = False
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Нажмите для открытия превью")

    def set_preview_pixmap(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        if pixmap is not None and not pixmap.isNull():
            scaled = QPixmap(pixmap).scaled(self.iconSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setIcon(QIcon(scaled))
            self.setText("")
        else:
            self.setIcon(QIcon())
            self.setText(self._placeholder_text)

    def set_placeholder(self, text: str) -> None:
        self._placeholder_text = text
        if self._pixmap is None:
            self.setText(text)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)

        if not self._hovered or not self.isEnabled():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        badge_size = 26
        badge_x = self.width() - badge_size - 6
        badge_y = 6
        painter.setBrush(QColor(0, 0, 0, 130))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(badge_x, badge_y, badge_size, badge_size)

        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 14))
        painter.drawText(badge_x, badge_y, badge_size, badge_size, Qt.AlignCenter, "\U0001F50D")


class ExportTabController:
    """Презентационный контроллер для вкладки экспорта PostGIS -> DXF."""

    _PREVIEW_SIZE = 128
    _ACTION_BUTTON_SIZE = 36

    def __init__(
        self,
        dialog,
        iface,
        connection_service: ConnectionConfigService,
        data_viewer_use_case: DataViewerUseCase,
        export_use_case: ExportUseCase,
        localization: ILocalization,
        logger: ILogger,
    ):
        self._dialog = dialog
        self._iface = iface
        self._connection_service = connection_service
        self._data_viewer_use_case = data_viewer_use_case
        self._export_use_case = export_use_case
        self._localization = localization
        self._logger = logger

        self._selected_connection: ConnectionConfigDTO | None = None
        self._export_schema = ""
        self._preview_dir = Path(__file__).resolve().parents[3] / "previews"
        self._thumbs_dir = self._preview_dir / ".thumbs"
        self._doc_info_cache: dict[str, dict] = {}
        self._pixmap_cache: dict[str, QPixmap] = {}
        self._pending_thumb_buttons: dict[str, list[_PreviewButton]] = {}
        self._thumb_queue: list[Path] = []
        self._thumb_queue_set: set[str] = set()
        self._thumb_generation_active = False

    def update_ui_language(self):
        self._dialog.db_tree_widget.setColumnCount(2)
        self._dialog.db_tree_widget.header().hide()
        self._update_export_ui()

    def update_connection_combo(self):
        configs = self._connection_service.get_all_configs()
        current_name = self._dialog.connection_combo.currentText()

        with QSignalBlocker(self._dialog.connection_combo):
            self._dialog.connection_combo.clear()
            self._dialog.connection_combo.addItem("")
            for config in configs:
                self._dialog.connection_combo.addItem(config.name)

            if current_name and self._dialog.connection_combo.findText(current_name) >= 0:
                self._dialog.connection_combo.setCurrentText(current_name)
            elif configs:
                self._dialog.connection_combo.setCurrentIndex(1)

        if not configs:
            self._selected_connection = None
            self._export_schema = ""
            with QSignalBlocker(self._dialog.schema_combo):
                self._dialog.schema_combo.clear()
            self._dialog.db_tree_widget.clear()
            self._update_export_ui()

    def on_connection_editor_button_click(self):
        from ...presentation.dialogs import ConnectionEditorDialog

        dialog = ConnectionEditorDialog(self._dialog)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_connection is not None:
            self.update_connection_combo()
            connection_name = dialog.selected_connection.name
            index = self._dialog.connection_combo.findText(connection_name)
            if index >= 0:
                self._dialog.connection_combo.setCurrentIndex(index)

    def on_connection_combo_changed(self, name: str):
        connection_name = (name or "").strip()
        if not connection_name:
            self._selected_connection = None
            self._export_schema = ""
            with QSignalBlocker(self._dialog.schema_combo):
                self._dialog.schema_combo.clear()
            self._dialog.db_tree_widget.clear()
            self._update_export_ui()
            return

        config = self._connection_service.get_config_by_name(connection_name)
        if config is None:
            self._selected_connection = None
            self._dialog.db_tree_widget.clear()
            self._update_export_ui()
            return

        self._selected_connection = config
        self._load_schemas_for_export()

    def on_schema_combo_changed(self, schema_name: str):
        self._export_schema = (schema_name or "").strip()
        self.refresh_db_files()

    def on_tab_activated(self):
        self.update_connection_combo()
        self.refresh_db_files()

    def on_export_clicked(self):
        if self._dialog.tabWidget.currentIndex() != 1:
            self._dialog.tabWidget.setCurrentIndex(1)

        from ...presentation.dialogs.export_dialog import ExportDialog

        dialog = ExportDialog(self._dialog)
        if dialog.exec_() != QDialog.Accepted:
            return

        destination = dialog.get_selected_destination()
        if destination not in ("file", "qgis"):
            return

        self._run_export(destination)

    def refresh_db_files(self):
        t0 = perf_counter()
        self._dialog.db_tree_widget.clear()
        self._doc_info_cache = {}
        self._pending_thumb_buttons = {}
        self._thumb_queue = []
        self._thumb_queue_set = set()
        self._thumb_generation_active = False

        if self._selected_connection is None or not self._export_schema:
            self._update_export_ui()
            return

        result = self._data_viewer_use_case.get_filenames(
            self._selected_connection,
            self._export_schema,
        )
        t_fetch = perf_counter()

        if result.is_fail:
            QMessageBox.warning(self._dialog, "Ошибка", f"Не удалось загрузить файлы БД: {result.error}")
            self._update_export_ui()
            return

        self._dialog.db_tree_widget.setUpdatesEnabled(False)
        preview_present = 0
        for filename in result.value:
            if not filename:
                continue
            item = QTreeWidgetItem([filename])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            item.setCheckState(0, Qt.Unchecked)
            self._dialog.db_tree_widget.addTopLevelItem(item)
            has_preview = (self._preview_dir / f"{Path(filename).stem}.svg").exists()
            if has_preview:
                preview_present += 1
            self._dialog.db_tree_widget.setItemWidget(item, 1, self._build_actions_widget(item, has_preview))

        if self._dialog.db_tree_widget.topLevelItemCount() == 0:
            empty_item = QTreeWidgetItem([self._localization.tr("MAIN_DIALOG", "db_files_empty")])
            empty_item.setFlags(Qt.ItemIsEnabled)
            self._dialog.db_tree_widget.addTopLevelItem(empty_item)

        self._dialog.db_tree_widget.setUpdatesEnabled(True)
        self._update_export_ui()

        if self._thumb_queue:
            self._thumb_generation_active = True
            QTimer.singleShot(0, self._process_thumb_queue_step)

        t_done = perf_counter()
        self._logger.message(
            "Export list refresh timings: "
            f"fetch={t_fetch - t0:.3f}s, "
            f"render={t_done - t_fetch:.3f}s, "
            f"total={t_done - t0:.3f}s, "
            f"files={len(result.value)}, previews={preview_present}"
        )

    def _build_actions_widget(self, item: QTreeWidgetItem, has_preview: bool) -> QWidget:
        container = QWidget(self._dialog.db_tree_widget)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        preview_column = QVBoxLayout()
        preview_column.setContentsMargins(0, 0, 0, 0)
        preview_column.setSpacing(4)

        filename = item.text(0)
        preview_path = self._preview_dir / f"{Path(filename).stem}.svg"

        preview_button = _PreviewButton(container)
        preview_button.setFixedSize(self._PREVIEW_SIZE, self._PREVIEW_SIZE)
        preview_button.setIconSize(preview_button.size())
        preview_button.setStyleSheet(
            "border: 1px solid #C9C9C9; border-radius: 4px; background: #FAFAFA;"
            "font-size: 12px; font-weight: 600; color: #606060;"
        )
        preview_button.clicked.connect(lambda: self._show_preview(str(preview_path)))

        load_preview_button = QPushButton("Подгрузить превью", container)
        load_preview_button.setFixedHeight(24)
        load_preview_button.clicked.connect(
            partial(
                self._on_load_preview_click,
                filename,
                preview_path,
                preview_button,
                load_preview_button,
            )
        )

        if has_preview:
            pixmap = self._get_cached_thumb_pixmap(preview_path)
            if pixmap is not None:
                preview_button.set_preview_pixmap(pixmap)
            else:
                preview_button.set_placeholder("SVG")
                key = str(preview_path)
                self._pending_thumb_buttons.setdefault(key, []).append(preview_button)
                if key not in self._thumb_queue_set:
                    self._thumb_queue.append(preview_path)
                    self._thumb_queue_set.add(key)
            load_preview_button.setVisible(False)
        else:
            preview_button.set_placeholder("N/A")
            preview_button.setEnabled(False)
            load_preview_button.setVisible(True)

        info_button = QPushButton("i", container)
        info_button.setFixedSize(self._ACTION_BUTTON_SIZE, self._ACTION_BUTTON_SIZE)
        info_button.setToolTip("Информация")
        info_button.clicked.connect(lambda _checked=False: self._show_document_info(item.text(0)))

        delete_button = QPushButton("x", container)
        delete_button.setFixedSize(self._ACTION_BUTTON_SIZE, self._ACTION_BUTTON_SIZE)
        delete_button.setToolTip("Удалить из БД")
        delete_button.clicked.connect(lambda _checked=False: self._delete_document(item.text(0)))

        preview_column.addWidget(preview_button)
        preview_column.addWidget(load_preview_button)

        layout.addLayout(preview_column)
        layout.addWidget(info_button)
        layout.addWidget(delete_button)
        layout.addStretch(1)

        return container

    def _on_load_preview_click(
        self,
        filename: str,
        preview_path: Path,
        preview_button: _PreviewButton,
        load_button: QPushButton,
    ) -> None:
        result = self._data_viewer_use_case.generate_preview_by_filename(
            self._selected_connection,
            self._export_schema,
            filename,
            str(self._preview_dir),
        )
        if result.is_fail:
            QMessageBox.critical(self._dialog, "Ошибка", f"Не удалось создать превью: {result.error}")
            return

        created_path = Path(result.value)
        pixmap = self._get_cached_thumb_pixmap(created_path)
        if pixmap is None:
            self._build_thumb_to_disk(created_path)
            pixmap = self._get_cached_thumb_pixmap(created_path)

        if pixmap is not None:
            preview_button.setEnabled(True)
            preview_button.set_preview_pixmap(pixmap)
            preview_button.clicked.disconnect()
            preview_button.clicked.connect(lambda: self._show_preview(str(preview_path)))
        else:
            preview_button.setEnabled(True)
            preview_button.set_placeholder("SVG")

        load_button.setVisible(False)

    def _show_preview(self, svg_path: str) -> None:
        if not os.path.exists(svg_path):
            QMessageBox.information(self._dialog, "Информация", "Превью не найдено")
            return

        dialog = SvgPreviewDialog(svg_path, self._dialog)
        dialog.exec_()

    def _show_document_info(self, filename: str) -> None:
        if not filename:
            return

        if filename not in self._doc_info_cache:
            result = self._data_viewer_use_case.get_document_info(
                self._selected_connection,
                self._export_schema,
                filename,
            )
            if result.is_fail:
                QMessageBox.critical(self._dialog, "Ошибка", f"Не удалось получить информацию: {result.error}")
                return
            self._doc_info_cache[filename] = result.value

        doc_meta = self._doc_info_cache[filename]
        upload_date = self._format_datetime(doc_meta.get("upload_date"))
        update_date = self._format_datetime(doc_meta.get("update_date"))
        size_text = self._format_size(doc_meta.get("file_size", 0))
        layer_count = doc_meta.get("layer_count", 0)
        preview_path = self._preview_dir / f"{Path(filename).stem}.svg"
        preview_state = "есть" if preview_path.exists() else "нет"

        message = QMessageBox(self._dialog)
        message.setWindowTitle("Информация о файле")
        message.setTextFormat(Qt.RichText)
        message.setText(
            (
                "<div style='min-width:320px'>"
                "<h3 style='margin:0 0 10px 0;'>Карточка DXF</h3>"
                "<table cellspacing='0' cellpadding='3'>"
                f"<tr><td><b>Файл:</b></td><td>{filename}</td></tr>"
                f"<tr><td><b>Схема:</b></td><td>{self._export_schema}</td></tr>"
                f"<tr><td><b>Размер:</b></td><td>{size_text}</td></tr>"
                f"<tr><td><b>Слоёв:</b></td><td>{layer_count}</td></tr>"
                f"<tr><td><b>Загружен:</b></td><td>{upload_date}</td></tr>"
                f"<tr><td><b>Обновлен:</b></td><td>{update_date}</td></tr>"
                f"<tr><td><b>Превью:</b></td><td>{preview_state}</td></tr>"
                "</table>"
                "</div>"
            )
        )
        message.exec_()

    def _format_datetime(self, value) -> str:
        if value is None:
            return "-"
        if isinstance(value, datetime):
            return value.strftime("%d.%m.%Y %H:%M:%S")
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.strftime("%d.%m.%Y %H:%M:%S")
        except Exception:
            return str(value)

    def _format_size(self, size_bytes: int) -> str:
        size = float(max(0, int(size_bytes or 0)))
        units = ["B", "KB", "MB", "GB"]
        idx = 0
        while size >= 1024 and idx < len(units) - 1:
            size /= 1024.0
            idx += 1
        if idx == 0:
            return f"{int(size)} {units[idx]}"
        return f"{size:.2f} {units[idx]}"

    def _get_cached_thumb_pixmap(self, svg_path: Path) -> QPixmap | None:
        cache_key = str(svg_path)
        cached = self._pixmap_cache.get(cache_key)
        if cached is not None and not cached.isNull():
            return cached

        try:
            self._thumbs_dir.mkdir(parents=True, exist_ok=True)
            thumb_path = self._thumbs_dir / f"{svg_path.stem}_{self._PREVIEW_SIZE}.png"

            if thumb_path.exists() and thumb_path.stat().st_mtime >= svg_path.stat().st_mtime:
                pixmap = QPixmap(str(thumb_path))
                if not pixmap.isNull():
                    self._pixmap_cache[cache_key] = pixmap
                    return pixmap
        except Exception as exc:
            self._logger.warning(f"Failed to load preview thumbnail '{svg_path}': {exc}")
            return None

        return None

    def _build_thumb_to_disk(self, svg_path: Path) -> bool:
        try:
            self._thumbs_dir.mkdir(parents=True, exist_ok=True)
            thumb_path = self._thumbs_dir / f"{svg_path.stem}_{self._PREVIEW_SIZE}.png"

            renderer = QSvgRenderer(str(svg_path))
            if not renderer.isValid():
                return False

            image = QImage(self._PREVIEW_SIZE, self._PREVIEW_SIZE, QImage.Format_ARGB32)
            image.fill(Qt.transparent)
            painter = QPainter(image)
            renderer.render(painter)
            painter.end()

            return image.save(str(thumb_path), "PNG")
        except Exception as exc:
            self._logger.warning(f"Failed to build preview thumbnail '{svg_path}': {exc}")
            return False

    def _process_thumb_queue_step(self) -> None:
        if not self._thumb_queue:
            self._thumb_generation_active = False
            return

        svg_path = self._thumb_queue.pop(0)
        key = str(svg_path)
        self._thumb_queue_set.discard(key)

        if svg_path.exists():
            self._build_thumb_to_disk(svg_path)

        pixmap = self._get_cached_thumb_pixmap(svg_path)
        if pixmap is not None:
            for button in self._pending_thumb_buttons.get(key, []):
                if button is not None and button.parent() is not None:
                    button.setEnabled(True)
                    button.set_preview_pixmap(pixmap)
        self._pending_thumb_buttons.pop(key, None)

        if self._thumb_queue:
            QTimer.singleShot(0, self._process_thumb_queue_step)
        else:
            self._thumb_generation_active = False

    def _delete_document(self, filename: str) -> None:
        if not filename:
            return

        reply = QMessageBox.question(
            self._dialog,
            "Удаление",
            f"Удалить '{filename}' из БД?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        result = self._data_viewer_use_case.delete_document_by_filename(
            self._selected_connection,
            self._export_schema,
            filename,
        )
        if result.is_fail:
            QMessageBox.critical(self._dialog, "Ошибка", f"Не удалось удалить файл: {result.error}")
            return

        if result.value:
            self._doc_info_cache.pop(filename, None)
            preview_path = self._preview_dir / f"{Path(filename).stem}.svg"
            if preview_path.exists():
                try:
                    preview_path.unlink()
                except Exception as exc:
                    self._logger.warning(f"Failed to delete preview '{preview_path}': {exc}")
            self.refresh_db_files()
        else:
            QMessageBox.information(self._dialog, "Информация", "Файл уже отсутствует в БД")

    def update_export_ui(self):
        self._update_export_ui()

    def _load_schemas_for_export(self):
        if self._selected_connection is None:
            return

        result = self._data_viewer_use_case.get_schemas(self._selected_connection)
        if result.is_fail:
            QMessageBox.warning(self._dialog, "Ошибка", f"Не удалось загрузить схемы: {result.error}")
            with QSignalBlocker(self._dialog.schema_combo):
                self._dialog.schema_combo.clear()
            self._dialog.db_tree_widget.clear()
            self._update_export_ui()
            return

        schemas = result.value

        with QSignalBlocker(self._dialog.schema_combo):
            self._dialog.schema_combo.clear()
            self._dialog.schema_combo.addItems(schemas)

            if self._export_schema and self._export_schema in schemas:
                self._dialog.schema_combo.setCurrentText(self._export_schema)
            elif schemas:
                self._dialog.schema_combo.setCurrentIndex(0)

        self._export_schema = self._dialog.schema_combo.currentText().strip()
        self.refresh_db_files()

    def _update_export_ui(self):
        has_connection = self._selected_connection is not None
        has_schema = bool(self._export_schema)
        has_files = any(
            self._dialog.db_tree_widget.topLevelItem(i).flags() & Qt.ItemIsUserCheckable
            for i in range(self._dialog.db_tree_widget.topLevelItemCount())
        )

        self._dialog.schema_label.setEnabled(has_connection)
        self._dialog.schema_combo.setEnabled(has_connection)
        self._dialog.refresh_db_button.setEnabled(has_connection and has_schema)
        self._dialog.db_tree_widget.setEnabled(has_connection and has_schema)
        self._dialog.export_db_button.setEnabled(has_connection and has_schema and has_files)

    def _get_selected_db_filenames(self) -> list[str]:
        selected_files: list[str] = []

        for i in range(self._dialog.db_tree_widget.topLevelItemCount()):
            item = self._dialog.db_tree_widget.topLevelItem(i)
            if item.flags() & Qt.ItemIsUserCheckable and item.checkState(0) == Qt.Checked:
                selected_files.append(item.text(0))

        if selected_files:
            return selected_files

        for item in self._dialog.db_tree_widget.selectedItems():
            if item.flags() & Qt.ItemIsUserCheckable:
                selected_files.append(item.text(0))

        return selected_files

    def _run_export(self, destination: str):
        selected_files = self._get_selected_db_filenames()
        if not selected_files:
            QMessageBox.information(
                self._dialog,
                "Информация",
                self._localization.tr("MAIN_DIALOG", "select_files_to_export"),
            )
            return

        if self._selected_connection is None:
            QMessageBox.warning(
                self._dialog,
                "Ошибка",
                self._localization.tr("MAIN_DIALOG", "select_connection_first"),
            )
            return

        if not self._export_schema:
            QMessageBox.warning(
                self._dialog,
                "Ошибка",
                self._localization.tr("MAIN_DIALOG", "select_schema_first"),
            )
            return

        export_mode = ExportMode.FILE if destination == "file" else ExportMode.QGIS
        output_dir = ""

        if export_mode == ExportMode.FILE:
            output_dir = QFileDialog.getExistingDirectory(
                self._dialog,
                self._localization.tr("MAIN_DIALOG", "choose_export_folder"),
            )
            if not output_dir:
                return

        export_configs: list[ExportConfigDTO] = []
        for filename in selected_files:
            output_path = os.path.join(output_dir, filename) if output_dir else ""
            export_configs.append(
                ExportConfigDTO(
                    filename=filename,
                    export_mode=export_mode,
                    output_path=output_path,
                    file_schema=self._export_schema,
                )
            )

        def export_task():
            return self._export_use_case.execute(self._selected_connection, export_configs)

        def _on_export_finished(result, progress_dialog):
            progress_dialog.close()
            app_result, report = result
            self._logger.message(report)

            if app_result.is_fail:
                QMessageBox.critical(self._dialog, "Ошибка", f"Экспорт завершился с ошибкой: {app_result.error}")
                return

            if export_mode == ExportMode.QGIS:
                loaded_count = self._load_exported_files_to_qgis(selected_files)
                QMessageBox.information(
                    self._dialog,
                    "Успех",
                    self._localization.tr("MAIN_DIALOG", "export_success_qgis", loaded_count),
                )
            else:
                QMessageBox.information(
                    self._dialog,
                    "Успех",
                    self._localization.tr("MAIN_DIALOG", "export_success_folder", output_dir),
                )

        def _on_export_error(error: str, progress_dialog):
            progress_dialog.close()
            QMessageBox.critical(self._dialog, "Ошибка", f"Ошибка экспорта: {error}")

        self.export_worker = LongTaskWorker(export_task)

        progress_dialog = QProgressDialog(
            self._localization.tr("MAIN_DIALOG", "export_in_progress"),
            self._localization.tr("MAIN_DIALOG", "cancel"),
            0,
            0,
            self._dialog,
        )
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(True)
        progress_dialog.setAutoReset(True)
        progress_dialog.repaint()

        self.export_worker.finished.connect(
            lambda task_id, result: _on_export_finished(result, progress_dialog)
        )
        self.export_worker.error.connect(
            lambda error: _on_export_error(error, progress_dialog)
        )

        self.export_worker.start()
        progress_dialog.exec_()

    def _load_exported_files_to_qgis(self, filenames: list[str]) -> int:
        loaded_count = 0
        for filename in filenames:
            file_path = os.path.join(tempfile.gettempdir(), filename)
            if not os.path.exists(file_path):
                continue

            layer_name = os.path.splitext(filename)[0]
            layer = self._iface.addVectorLayer(file_path, layer_name, "ogr")
            if layer:
                loaded_count += 1

        return loaded_count
