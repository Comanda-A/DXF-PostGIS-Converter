from __future__ import annotations

from uuid import UUID
from ...domain.entities import DXFBase, DXFDocument, DXFLayer
from ...domain.repositories import IActiveDocumentRepository

from ...application.dtos import DXFDocumentDTO
from ...application.mappers import DXFMapper
from ...application.results import AppResult
from ...application.events import IAppEvents
from ...application.interfaces import ILogger

class SelectEntityUseCase:
    """Вариант использования: Выбрать объект"""

    def __init__(self, active_repo: IActiveDocumentRepository, app_events: IAppEvents, logger: ILogger):
        self._active_repo = active_repo
        self._app_events = app_events
        self._logger = logger
    
    def execute(self, entities: dict[UUID, bool]) -> AppResult[list[DXFDocumentDTO]]:
        """Выбрать несколько объектов. {entity_id: selected}"""

        if not entities:
            return AppResult.fail("No entities provided for select")
        
        # Получаем все документы
        result = self._active_repo.get_all()
        if result.is_fail:
            return AppResult.fail(result.error)
        
        documents = result.value
        modified_documents: dict[UUID, DXFDocument] = {}

        for entity_id, selected in entities.items():
            target_doc, entity = self._find_entity_by_id(documents, entity_id)
            if entity is None or target_doc is None:
                continue

            self._set_selected_recursive(entity, selected)
            modified_documents[target_doc.id] = target_doc
        
        updated_docs = list(modified_documents.values())
        for doc in updated_docs[:]:
            result = self._active_repo.update(doc)
            if result.is_fail:
                self._logger.error(f"Error updating active documents: {result.error}")
                updated_docs.remove(doc)
        
        dtos = DXFMapper.to_dto(updated_docs)
        self._app_events.on_document_modified.emit(dtos)
        return AppResult.success(dtos)
    
    def execute_single(self, entity_id: UUID, selected: bool) -> AppResult[DXFDocumentDTO]:
        
        result = self.execute({entity_id: selected})
        
        if result.is_fail:
            return AppResult.fail(result.error)
        
        if len(result.value) >= 1:
            return AppResult.success(result.value[0])
        
        return AppResult.fail(f"Unexpected error: object '{entity_id}' was not returned in result")
    
    def _find_entity_by_id(self, documents: list[DXFDocument], entity_id: UUID) -> tuple[DXFDocument | None, DXFBase | None]:

        for document in documents:
            # Проверяем документ
            if document.id == entity_id:
                return document, document
            
            # Проверяем слои документа
            if entity_id in document.layers:
                return document, document.layers[entity_id]
            
            # Проверяем сущности в слоях
            for layer in document.layers.values():
                if entity_id in layer.entities:
                    return document, layer.entities[entity_id]
        
        return None, None

    def _set_selected_recursive(self, entity: DXFBase, selected: bool) -> None:
        entity.set_selected(selected)

        if isinstance(entity, DXFDocument):
            for layer in entity.layers.values():
                self._set_selected_recursive(layer, selected)
            return

        if isinstance(entity, DXFLayer):
            for layer_entity in entity.entities.values():
                self._set_selected_recursive(layer_entity, selected)