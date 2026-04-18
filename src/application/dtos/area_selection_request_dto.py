from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...domain.value_objects import SelectionMode, SelectionRule, ShapeType


@dataclass(frozen=True)
class AreaSelectionRequestDTO:
    """Параметры выбора области на уровне application-слоя.

    Использует доменные enum-ы, чтобы избежать дублирования типов.
    """

    shape: ShapeType
    selection_rule: SelectionRule
    selection_mode: SelectionMode
    shape_args: tuple[Any, ...]
