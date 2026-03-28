
from abc import abstractmethod
from ...domain.value_objects import Result, DxfEntityType
from ...domain.entities import DXFEntity
from ...domain.repositories import IRepository


class IEntityRepository(IRepository[DXFEntity]):
    """Репозиторий для сущностей"""
    
    @abstractmethod
    def get_by_name_and_type(self, name: str, type: DxfEntityType) -> Result[DXFEntity | None]:
        """Получить по имени"""
        pass

    @abstractmethod
    def get_all(self) -> list[DXFEntity]:
        """Все сохраненные сущности"""
        pass
