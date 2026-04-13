from __future__ import annotations

import os
from typing import Any

import inject

from qgis.PyQt.QtCore import QObject
from qgis.core import QgsProject, QgsLayerTreeGroup, QgsLayerTreeLayer

from ...application.events import IAppEvents
from ...application.interfaces import ILogger
from ...application.services import ActiveDocumentService
from ...application.use_cases import SelectEntityUseCase


class QGISLayerSyncManager(QObject):
    """
    Менеджер синхронизации между деревом плагина и панелью слоев QGIS.
    Обеспечивает двустороннюю синхронизацию состояния checkbox-ов.
    """
    
    @inject.autoparams(
        "active_doc_service",
        "select_entity_use_case",
        "app_events",
        "logger",
    )
    def __init__(
        self,
        active_doc_service: ActiveDocumentService,
        select_entity_use_case: SelectEntityUseCase,
        app_events: IAppEvents,
        logger: ILogger,
    ):
        super().__init__()
        self._active_doc_service = active_doc_service
        self._select_entity_use_case = select_entity_use_case
        self._app_events = app_events
        self._logger = logger
        self.project = QgsProject.instance()
        self.layer_tree = self.project.layerTreeRoot()
        self.sync_mapping: dict[str, dict[str, Any]] = {}
        self._connected_nodes: list[Any] = []
        self._sync_guard = False

        self._app_events.on_document_opened.connect(self._on_documents_changed)
        self._app_events.on_document_closed.connect(self._on_documents_changed)
        self._app_events.on_document_modified.connect(self._on_documents_changed)

    def sync_now(self) -> None:
        """Полная синхронизация состояния слоёв между моделью и деревом QGIS."""
        self._rebuild_mapping()
        self._apply_model_state_to_qgis()
    
    def _find_group_by_name(self, group_name: str):
        """
        Ищет группу по имени в корне дерева слоев QGIS.
        
        Args:
            group_name: Имя группы для поиска
            
        Returns:
            QgsLayerTreeGroup или None если не найдено
        """
        for child in self.layer_tree.children():
            if isinstance(child, QgsLayerTreeGroup) and child.name() == group_name:
                return child
        return None

    def _find_child_group_by_name(self, parent_group: QgsLayerTreeGroup, group_name: str):
        """
        Ищет дочернюю группу по имени в родительской группе.
        
        Args:
            parent_group: Родительская группа
            group_name: Имя дочерней группы для поиска
            
        Returns:
            QgsLayerTreeGroup или None если не найдено
        """
        for child in parent_group.children():
            if isinstance(child, QgsLayerTreeGroup) and child.name() == group_name:
                return child
        return None

    def _find_child_layer_by_name(self, parent_group: QgsLayerTreeGroup, layer_name: str):
        for child in parent_group.children():
            if not isinstance(child, QgsLayerTreeLayer):
                continue
            layer = child.layer()
            if layer and layer.name() == layer_name:
                return child
        return None

    def _connect_node(self, node) -> None:
        if node in self._connected_nodes:
            return
        try:
            node.visibilityChanged.connect(self._on_qgis_visibility_changed)
            self._connected_nodes.append(node)
        except Exception as e:
            self._logger.warning(f"Cannot connect node visibility signal: {e}")

    def _disconnect_all_nodes(self) -> None:
        for node in self._connected_nodes:
            try:
                node.visibilityChanged.disconnect(self._on_qgis_visibility_changed)
            except Exception:
                pass
        self._connected_nodes = []

    def _make_file_name_candidates(self, file_name: str) -> list[str]:
        stem = os.path.splitext(file_name)[0]
        base = stem.split("_")[0]
        candidates = [file_name, stem, base]
        unique: list[str] = []
        for candidate in candidates:
            if candidate and candidate not in unique:
                unique.append(candidate)
        return unique

    def _find_file_group(self, file_name: str):
        for candidate in self._make_file_name_candidates(file_name):
            group = self._find_group_by_name(candidate)
            if group is not None:
                return group
        return None

    def _find_layer_node(self, file_group: QgsLayerTreeGroup, layer_name: str):
        layer_group = self._find_child_group_by_name(file_group, layer_name)
        if layer_group is not None:
            return layer_group
        return self._find_child_layer_by_name(file_group, layer_name)

    def _rebuild_mapping(self) -> None:
        self._disconnect_all_nodes()
        self.sync_mapping = {}

        for doc in self._active_doc_service.get_all():
            file_group = self._find_file_group(doc.filename)
            if file_group is None:
                continue

            layers: dict[str, Any] = {}
            layer_ids: dict[str, Any] = {}

            for layer in doc.layers:
                layer_node = self._find_layer_node(file_group, layer.name)
                if layer_node is None:
                    continue
                layers[layer.name] = layer_node
                layer_ids[layer.name] = layer.id
                self._connect_node(layer_node)

            self._connect_node(file_group)
            self.sync_mapping[doc.filename] = {
                "file_group": file_group,
                "layers": layers,
                "layer_ids": layer_ids,
            }

    def _set_node_checked(self, node, checked: bool) -> None:
        if bool(node.itemVisibilityChecked()) == bool(checked):
            return
        node.setItemVisibilityChecked(bool(checked))

    def _update_file_group_state(self, file_group: QgsLayerTreeGroup, layer_nodes: dict[str, Any]) -> None:
        if not layer_nodes:
            return

        any_checked = any(bool(node.itemVisibilityChecked()) for node in layer_nodes.values())
        self._set_node_checked(file_group, any_checked)

    def _apply_model_state_to_qgis(self) -> None:
        self._sync_guard = True
        try:
            for doc in self._active_doc_service.get_all():
                mapping = self.sync_mapping.get(doc.filename)
                if not mapping:
                    continue

                layer_nodes = mapping.get("layers", {})
                for layer in doc.layers:
                    node = layer_nodes.get(layer.name)
                    if node is None:
                        continue
                    self._set_node_checked(node, bool(layer.selected))

                file_group = mapping.get("file_group")
                if file_group is not None:
                    self._update_file_group_state(file_group, layer_nodes)
        finally:
            self._sync_guard = False

    def _on_documents_changed(self, _payload) -> None:
        self.sync_now()

    def _find_doc_layer_id(self, file_name: str, layer_name: str):
        mapping = self.sync_mapping.get(file_name)
        if not mapping:
            return None
        layer_ids = mapping.get("layer_ids", {})
        return layer_ids.get(layer_name)

    def _on_qgis_visibility_changed(self, node) -> None:
        if self._sync_guard:
            return

        try:
            checked = bool(node.itemVisibilityChecked())

            for file_name, mapping in self.sync_mapping.items():
                file_group = mapping.get("file_group")
                layers = mapping.get("layers", {})

                if file_group == node:
                    entities = {}
                    for layer_name in layers.keys():
                        layer_id = self._find_doc_layer_id(file_name, layer_name)
                        if layer_id is not None:
                            entities[layer_id] = checked

                    if entities:
                        result = self._select_entity_use_case.execute(entities)
                        if result.is_fail:
                            self._logger.error(f"QGIS->plugin sync failed for file '{file_name}': {result.error}")
                    return

                for layer_name, layer_node in layers.items():
                    if layer_node != node:
                        continue

                    layer_id = self._find_doc_layer_id(file_name, layer_name)
                    if layer_id is None:
                        return

                    result = self._select_entity_use_case.execute_single(layer_id, checked)
                    if result.is_fail:
                        self._logger.error(
                            f"QGIS->plugin sync failed for layer '{file_name}/{layer_name}': {result.error}"
                        )
                    return
        except Exception as e:
            self._logger.error(f"QGIS visibility sync error: {e}")
