
from uuid import UUID
from ...domain.repositories import IActiveDocumentRepository
from ...domain.services import IDXFWriter
from ...application.results import AppResult, Unit
from ...application.events import IAppEvents

class CloseDocumentUseCase:
    """Вариант использования: Закрыть DXF файл"""

    def __init__(self, active_repo: IActiveDocumentRepository, dxf_writer: IDXFWriter, app_events: IAppEvents):
        self._active_repo = active_repo
        self._dxf_writer = dxf_writer
        self._app_events = app_events
    
    def execute(self, document_id: UUID) -> AppResult[Unit]:
        result = self._active_repo.remove(document_id)
        if result.is_success:
            self._app_events.on_document_closed.emit(document_id)
            return AppResult.success(Unit())
        return AppResult.fail(result.error)