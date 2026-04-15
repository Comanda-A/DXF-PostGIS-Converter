from __future__ import annotations

from abc import ABC, abstractmethod

from ...domain.value_objects import Result, AreaSelectionParams


class IAreaSelector(ABC):
    @abstractmethod
    def select_handles(
        self,
        filepath: str,
        params: AreaSelectionParams,
    ) -> Result[list[str]]:
        """Возвращает список handle сущностей, попавших в область выбора."""
        pass
