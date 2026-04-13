
import inject, os
from .domain.services import IDXFReader, IDXFWriter, IAreaSelector
from .domain.repositories import IActiveDocumentRepository, IConnectionFactory, IRepositoryFactory

from .application.interfaces import ISettings, ILogger, ILocalization
from .application.events import IEvent, IAppEvents
from .application.services import ActiveDocumentService, ConnectionConfigService
from .application.database import DBSession
from .application.use_cases import OpenDocumentUseCase, CloseDocumentUseCase, SelectEntityUseCase, SelectAreaUseCase, ImportUseCase, ExportUseCase, DataViewerUseCase, SaveSelectedToFileUseCase

from .infrastructure.qgis import Settings, Logger, QtEvent, QtAppEvents
from .infrastructure.localization.localization import Localization
from .infrastructure.ezdxf import DXFReader, EzdxfAreaSelector
from .infrastructure.database import (
    ActiveDocumentRepository,
    ConnectionFactory,
    RepositoryFactory
)
from .infrastructure.database.postgis import (
    PostGISConnection,
    PostGISDocumentRepository,
    PostGISLayerRepository,
    PostGISEntityRepository,
    PostGISContentRepository
)


class Container:

    @classmethod
    def configure_di(cls):
        """Конфигурация DI"""
        def config(binder: inject.Binder):
            # Создаем экземпляры
            app_events = QtAppEvents()
            settings = Settings()
            logger = Logger(settings)
            localization = Localization(settings, logger, app_events)
            dxfreader = DXFReader()
            area_selector = EzdxfAreaSelector()
            #dxfwriter = DXFWriter()
            active_repo = ActiveDocumentRepository()
            active_doc_service = ActiveDocumentService(active_repo, logger)
            
            open_use_case = OpenDocumentUseCase(active_repo, dxfreader, app_events, logger)
            close_use_case = CloseDocumentUseCase(active_repo, dxfreader, app_events)
            select_use_case = SelectEntityUseCase(active_repo, app_events, logger)
            select_area_use_case = SelectAreaUseCase(active_repo, area_selector, app_events, logger)
            import_use_case = ImportUseCase(active_repo, logger)
            export_use_case = ExportUseCase(logger)
            data_viewer_use_case = DataViewerUseCase(logger)
            save_selected_to_file_use_case = SaveSelectedToFileUseCase(active_repo, logger)

            # Реализации репозиториев и подключений к разным БД
            connection_factory = ConnectionFactory([PostGISConnection])
            repository_factory = RepositoryFactory()
            repository_factory.register_repositories(
                connection_type=PostGISConnection, 
                document_repo_class=PostGISDocumentRepository,
                layer_repo_class=PostGISLayerRepository,
                entity_repo_class=PostGISEntityRepository,
                content_repo_class=PostGISContentRepository
            )
            
            connection_config_service = ConnectionConfigService(
                os.path.join(os.path.dirname(__file__), '..', 'data'),
                connection_factory,
                logger
            )
            
            # Привязываем интерфейсы к конкретным экземплярам (синглтоны)
            binder.bind(IAppEvents, app_events)
            binder.bind(ISettings, settings)
            binder.bind(ILogger, logger)
            binder.bind(ILocalization, localization)
            binder.bind(IDXFReader, dxfreader)
            binder.bind(IAreaSelector, area_selector)
            binder.bind(IActiveDocumentRepository, active_repo)
            binder.bind(ActiveDocumentService, active_doc_service)
            binder.bind(ConnectionConfigService, connection_config_service)
            
            binder.bind(OpenDocumentUseCase, open_use_case)
            binder.bind(CloseDocumentUseCase, close_use_case)
            binder.bind(SelectEntityUseCase, select_use_case)
            binder.bind(SelectAreaUseCase, select_area_use_case)
            binder.bind(ImportUseCase, import_use_case)
            binder.bind(ExportUseCase, export_use_case)
            binder.bind(DataViewerUseCase, data_viewer_use_case)
            binder.bind(SaveSelectedToFileUseCase, save_selected_to_file_use_case)

            binder.bind(IConnectionFactory, connection_factory)
            binder.bind(IRepositoryFactory, repository_factory)
            
            binder.bind_to_constructor(IEvent, lambda: QtEvent())
            binder.bind_to_constructor(DBSession, lambda: DBSession(connection_factory, repository_factory, logger))
        
        inject.configure(config, clear=True)