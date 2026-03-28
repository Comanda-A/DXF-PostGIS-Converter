
from ...domain.entities import DXFDocument
from ...domain.repositories import IActiveDocumentRepository
from ...domain.services import IDXFReader

from ...application.dtos import DXFDocumentDTO
from ...application.mappers import DXFMapper
from ...application.results import AppResult
from ...application.events import IAppEvents
from ...application.interfaces import ILogger

class OpenDocumentUseCase:
    """Вариант использования: Открыть DXF файл"""

    def __init__(
        self,
        active_repo: IActiveDocumentRepository,
        dxf_reader: IDXFReader,
        app_events: IAppEvents,
        logger: ILogger
    ):
        self._active_repo = active_repo
        self._dxf_reader = dxf_reader
        self._app_events = app_events
        self._logger = logger
    
    def execute(self, filepaths: list[str]) -> AppResult[list[DXFDocumentDTO]]:
        """Открыть несколько DXF файлов"""
        
        if not filepaths:
            return AppResult.fail("No files provided to open")

        opened_files: list[DXFDocument] = []

        for filepath in filepaths:
            # Открываем DXF файл
            open_result = self._dxf_reader.open(filepath)

            if open_result.is_fail:
                self._logger.error(f"Failed to open file '{filepath}': {open_result.error}")
                continue

            create_result = self._active_repo.create(open_result.value)

            if create_result.is_fail:
                self._logger.error(f"Failed to save document for '{filepath}': {create_result.error}")
                continue

            opened_files.append(create_result.value)

        if not opened_files:
            return AppResult.fail(f"Failed to open any file")
        
        # Если сохранение прошло успешно, возвращаем DTO документа
        dtos = DXFMapper.to_dto(opened_files)
        self._app_events.on_document_opened.emit(dtos)
        return AppResult.success(dtos)
    
    def execute_single(self, filepath: str) -> AppResult[DXFDocumentDTO]:
        
        result = self.execute([filepath])
        
        if result.is_fail:
            return AppResult.fail(result.error)
        
        if len(result.value) >= 1:
            return AppResult.success(result.value[0])
        
        return AppResult.fail(f"Unexpected error: object '{filepath}' was not returned in result")
