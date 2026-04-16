from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from time import perf_counter

from PyQt5.QtWidgets import (
    QMessageBox,
    QTreeWidgetItem,
    QDialog,
    QFileDialog,
    QWidget,
)
from PyQt5.QtCore import Qt, QSignalBlocker
from PyQt5.QtCore import QTimer

from ...application.dtos import ConnectionConfigDTO, ExportConfigDTO, ExportMode
from ...application.interfaces import ILocalization, ILogger
from ...application.services import ConnectionConfigService
from ...application.use_cases import DataViewerUseCase, ExportUseCase
from ...presentation.services.progress_task_runner import ProgressTaskRunner
from ...presentation.widgets import SvgPreviewDialog, DbTreeWidgetHandler

class ExportTabController:
    """Презентационный контроллер для вкладки экспорта PostGIS -> DXF."""

    def __init__(
        self,
        dialog,
        iface,
        connection_service: ConnectionConfigService,
        data_viewer_use_case: DataViewerUseCase,
        export_use_case: ExportUseCase,
        localization: ILocalization,
        logger: ILogger,
        on_qgis_export_ready: Callable[[list[str]], None] | None = None,
    ):
        self._dialog = dialog
        self._iface = iface
        self._connection_service = connection_service
        self._data_viewer_use_case = data_viewer_use_case
        self._export_use_case = export_use_case
        self._localization = localization
        self._logger = logger
        self._on_qgis_export_ready = on_qgis_export_ready

        self._selected_connection: ConnectionConfigDTO | None = None
        self._export_schema = ""
        self._preview_dir = Path(__file__).resolve().parents[3] / "previews"
        self._doc_info_cache: dict[str, dict] = {}

        # Инициализируем обработчик db_tree_widget
        self._db_tree_handler = DbTreeWidgetHandler(
            self._dialog.db_tree_widget,
            localization=localization,
            logger=logger,
            on_preview_click=self._on_db_preview_click,
            on_info_click=self._on_db_info_click,
            on_delete_click=self._on_db_delete_click,
            parent=self._dialog
        )

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
            self._db_tree_handler.clear()
            self._update_export_ui()

    def _on_db_preview_click(self, filename: str):
        """Callback когда нажата кнопка превью в db_tree_widget"""
        pass  # Превью открывается непосредственно в DbTreeWidgetHandler

    def _on_db_info_click(self, filename: str):
        """Callback когда нажата кнопка инфо в db_tree_widget"""
        self._show_document_info(filename)

    def _on_db_delete_click(self, filename: str):
        """Callback когда нажата кнопка удалить в db_tree_widget"""
        self._delete_document(filename)

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
            self._db_tree_handler.clear()
            self._update_export_ui()
            return

        config = self._connection_service.get_config_by_name(connection_name)
        if config is None:
            self._selected_connection = None
            self._db_tree_handler.clear()
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
        self._db_tree_handler.clear()
        self._doc_info_cache = {}

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
            has_preview = (self._preview_dir / f"{Path(filename).stem}.svg").exists()
            if has_preview:
                preview_present += 1
            self._db_tree_handler.add_item(filename, has_preview)

        if self._dialog.db_tree_widget.topLevelItemCount() == 0:
            empty_item = QTreeWidgetItem([self._localization.tr("MAIN_DIALOG", "db_files_empty")])
            empty_item.setFlags(Qt.ItemIsEnabled)
            self._dialog.db_tree_widget.addTopLevelItem(empty_item)

        self._dialog.db_tree_widget.setUpdatesEnabled(True)
        self._update_export_ui()

        t_done = perf_counter()
        self._logger.message(
            "Export list refresh timings: "
            f"fetch={t_fetch - t0:.3f}s, "
            f"render={t_done - t_fetch:.3f}s, "
            f"total={t_done - t0:.3f}s, "
            f"files={len(result.value)}, previews={preview_present}"
        )



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
            self._db_tree_handler.clear()
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
        self._db_tree_handler.set_enabled(has_connection and has_schema)
        self._dialog.export_db_button.setEnabled(has_connection and has_schema and has_files)

    def _get_selected_db_filenames(self) -> list[str]:
        """Get selected database filenames from handler."""
        # Try to get checked items first
        selected_files = self._db_tree_handler.get_checked_items()
        
        # If no checked items, try selected items
        if not selected_files:
            selected_files = self._db_tree_handler.get_selected_items()
        
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

        def _on_export_finished(result):
            app_result, report = result
            self._logger.message(report)

            if app_result.is_fail:
                QMessageBox.critical(self._dialog, "Ошибка", f"Экспорт завершился с ошибкой: {app_result.error}")
                return

            if export_mode == ExportMode.QGIS:
                exported_paths = self._resolve_exported_paths(selected_files)
                opened = self._open_qgis_import_dialog(exported_paths)

                if self._on_qgis_export_ready is not None and exported_paths:
                    self._on_qgis_export_ready(exported_paths)

                if opened:
                    QMessageBox.information(
                        self._dialog,
                        "Успех",
                        "Файлы экспортированы. Окно DXF Import открыто с готовым списком файлов.",
                    )
                else:
                    QMessageBox.warning(
                        self._dialog,
                        "Предупреждение",
                        "Файлы экспортированы, но не удалось открыть окно DXF Import.",
                    )
            else:
                QMessageBox.information(
                    self._dialog,
                    "Успех",
                    self._localization.tr("MAIN_DIALOG", "export_success_folder", output_dir),
                )

        def _on_export_error(error: str):
            QMessageBox.critical(self._dialog, "Ошибка", f"Ошибка экспорта: {error}")

        self.export_worker = ProgressTaskRunner.run(
            self._dialog,
            export_task,
            on_finished=_on_export_finished,
            on_error=_on_export_error,
            progress_text=self._localization.tr("MAIN_DIALOG", "export_in_progress"),
            cancel_text=self._localization.tr("MAIN_DIALOG", "cancel"),
        )

    def _resolve_exported_paths(self, filenames: list[str]) -> list[str]:
        existing_paths: list[str] = []
        for filename in filenames:
            file_path = os.path.join(tempfile.gettempdir(), filename)
            if os.path.exists(file_path):
                existing_paths.append(file_path)

        return existing_paths

    def _open_qgis_import_dialog(self, existing_paths: list[str]) -> bool:

        if not existing_paths:
            return False

        try:
            # Открываем тот же плагинный диалог DXF, как в конвертере, уже с готовым списком файлов.
            from ...plugins.dxf_tools.clsADXF2Shape import clsADXF2Shape

            adxf2shape = clsADXF2Shape(self._iface)
            dlg = adxf2shape.dlg

            dlg.current_files = existing_paths
            dlg.listDXFDatNam.clear()
            dlg.listDXFDatNam.setEnabled(True)
            for file_path in existing_paths:
                dlg.listDXFDatNam.addItem(file_path.replace("\\", "/"))

            if dlg.listDXFDatNam.count() > 0:
                dlg.listDXFDatNam.item(0).setSelected(True)
                if hasattr(dlg, "wld4listDXFDatNam"):
                    dlg.wld4listDXFDatNam()

            # Для последующего запуска импорта в проект QGIS оставляем соответствующие опции.
            if hasattr(dlg, "chkQgis"):
                dlg.chkQgis.setChecked(True)
            if hasattr(dlg, "chkSHP"):
                dlg.chkSHP.setChecked(False)
            if hasattr(dlg, "chkGPKG"):
                dlg.chkGPKG.setChecked(False)

            adxf2shape.run()
            return True
        except Exception as exc:
            self._logger.warning(f"Failed to open plugin-based QGIS import dialog: {exc}")
            return False
