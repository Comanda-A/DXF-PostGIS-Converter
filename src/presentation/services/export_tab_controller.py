from __future__ import annotations

import os
import tempfile

from qgis.PyQt.QtWidgets import QMessageBox, QTreeWidgetItem, QDialog, QFileDialog, QProgressDialog
from qgis.PyQt.QtCore import Qt, QSignalBlocker

from ...application.dtos import ConnectionConfigDTO, ExportConfigDTO, ExportMode
from ...application.interfaces import ILocalization, ILogger
from ...application.services import ConnectionConfigService
from ...application.use_cases import DataViewerUseCase, ExportUseCase
from ...presentation.workers import LongTaskWorker


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

    def update_ui_language(self):
        self._dialog.db_tree_widget.setColumnCount(1)
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
        self._dialog.db_tree_widget.clear()

        if self._selected_connection is None or not self._export_schema:
            self._update_export_ui()
            return

        result = self._data_viewer_use_case.get_filenames(
            self._selected_connection,
            self._export_schema,
        )

        if result.is_fail:
            QMessageBox.warning(self._dialog, "Ошибка", f"Не удалось загрузить файлы БД: {result.error}")
            self._update_export_ui()
            return

        for filename in result.value:
            item = QTreeWidgetItem([filename])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            item.setCheckState(0, Qt.Unchecked)
            self._dialog.db_tree_widget.addTopLevelItem(item)

        if self._dialog.db_tree_widget.topLevelItemCount() == 0:
            empty_item = QTreeWidgetItem([self._localization.tr("MAIN_DIALOG", "db_files_empty")])
            empty_item.setFlags(Qt.ItemIsEnabled)
            self._dialog.db_tree_widget.addTopLevelItem(empty_item)

        self._update_export_ui()

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
