
from uuid import UUID
from ...domain.entities import DXFBase, DXFDocument
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
        modified_documents = []
        
        # Для каждого ID ищем объект
        for entity_id, selected in entities.items():
            for doc in documents:
                entity = self._find_entity_by_id([doc], entity_id)
            
                if entity:
                    entity.set_selected(selected)
                    if doc not in modified_documents:
                        modified_documents.append(doc)
        
        for doc in modified_documents[:]:
            result = self._active_repo.update(doc)
            if result.is_fail:
                self._logger.error(f"Error updating active documents: {result.error}")
                modified_documents.remove(doc)
        
        dtos = DXFMapper.to_dto(modified_documents)
        self._app_events.on_document_modified.emit(dtos)
        return AppResult.success(dtos)
    
    def execute_single(self, entity_id: UUID, selected: bool) -> AppResult[DXFDocumentDTO]:
        
        result = self.execute({entity_id: selected})
        
        if result.is_fail:
            return AppResult.fail(result.error)
        
        if len(result.value) >= 1:
            return AppResult.success(result.value[0])
        
        return AppResult.fail(f"Unexpected error: object '{entity_id}' was not returned in result")
    
    def _find_entity_by_id(self, documents: list[DXFDocument], entity_id: UUID) -> DXFBase | None:

        for document in documents:
            # Проверяем документ
            if document.id == entity_id:
                return document
            
            # Проверяем слои документа
            if entity_id in document.layers:
                return document.layers[entity_id]
            
            # Проверяем сущности в слоях
            for layer in document.layers.values():
                if entity_id in layer.entities:
                    return layer.entities[entity_id]
        
        return None