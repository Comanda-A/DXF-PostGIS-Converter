from __future__ import annotations

from ...application.dtos import DXFDocumentDTO
from ...application.events import IAppEvents
from ...application.interfaces import ILogger
from ...application.mappers import DXFMapper
from ...application.results import AppResult
from ...domain.entities import DXFDocument
from ...domain.repositories import IActiveDocumentRepository
from ...domain.services import IAreaSelector
from ...domain.value_objects import AreaSelectionParams


class SelectAreaUseCase:
    """Вариант использования: выбор сущностей по области на карте."""

    def __init__(
        self,
        active_repo: IActiveDocumentRepository,
        area_selector: IAreaSelector,
        app_events: IAppEvents,
        logger: ILogger,
    ):
        self._active_repo = active_repo
        self._area_selector = area_selector
        self._app_events = app_events
        self._logger = logger

    def execute(
        self,
        filename: str,
        params: AreaSelectionParams,
    ) -> AppResult[DXFDocumentDTO]:
        self._logger.message(
            f"SelectAreaUseCase started: file='{filename}', shape={params.shape_type.value}, "
            f"rule={params.selection_rule.value}, mode={params.selection_mode.value}, "
            f"args_count={len(params.shape_args)}"
        )

        if not filename:
            return AppResult.fail("No filename provided")

        doc_result = self._active_repo.get_by_filename(filename)
        if doc_result.is_fail:
            return AppResult.fail(doc_result.error)

        document = doc_result.value
        if not document:
            return AppResult.fail(f"Document '{filename}' not found")

        if not document.filepath:
            return AppResult.fail(f"Document '{filename}' has no filepath")

        try:
            select_result = self._area_selector.select_handles(
                document.filepath,
                params,
            )
            if select_result.is_fail:
                self._logger.error(f"Area selector failed: {select_result.error}")
                return AppResult.fail(select_result.error)

            selected_handles = set(select_result.value)
            self._logger.message(f"Area selector returned handles: {len(selected_handles)}")

            changed_count = 0
            total_count = 0
            for layer in document.layers.values():
                for entity in layer.entities.values():
                    total_count += 1
                    handle = str(entity.attributes.get("handle", "")).strip().lower()
                    new_selected = handle in selected_handles and handle != ""
                    if entity.is_selected != new_selected:
                        changed_count += 1
                    entity.set_selected(new_selected)

            self._logger.message(
                f"Selection synced from ezdxf result: changed_entities={changed_count}, "
                f"total_entities={total_count}"
            )
            
            self._refresh_parent_selection(document)

            update_result = self._active_repo.update(document)
            if update_result.is_fail:
                return AppResult.fail(update_result.error)

            dto = DXFMapper.to_dto(document)
            self._app_events.on_document_modified.emit([dto])
            self._logger.message("SelectAreaUseCase completed successfully")
            return AppResult.success(dto)
        except Exception as e:
            self._logger.error(f"Select area failed for '{filename}': {e}")
            return AppResult.fail(str(e))

    def _refresh_parent_selection(self, document: DXFDocument):
        any_doc_selected = False

        for layer in document.layers.values():
            any_layer_selected = any(entity.is_selected for entity in layer.entities.values())
            layer.set_selected(any_layer_selected)
            any_doc_selected = any_doc_selected or any_layer_selected

        document.set_selected(any_doc_selected)
