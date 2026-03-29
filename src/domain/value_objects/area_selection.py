from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SelectionRule(Enum):
    INSIDE = "inside"
    OUTSIDE = "outside"
    INTERSECT = "intersect"


class ShapeType(Enum):
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    POLYGON = "polygon"


class SelectionMode(Enum):
    JOIN = "join"
    REPLACE = "replace"
    SUBTRACT = "subtract"


@dataclass(frozen=True)
class AreaSelectionParams:
    shape_type: ShapeType
    selection_rule: SelectionRule
    selection_mode: SelectionMode
    shape_args: tuple[Any, ...]
