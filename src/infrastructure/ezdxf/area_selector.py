from __future__ import annotations

import ezdxf
from ezdxf import select

from ...domain.services import IAreaSelector
from ...domain.value_objects import Result, AreaSelectionParams, ShapeType, SelectionRule


class EzdxfAreaSelector(IAreaSelector):
    def select_handles(
        self,
        filepath: str,
        params: AreaSelectionParams,
    ) -> Result[list[str]]:
        try:
            drawing = ezdxf.readfile(filepath)
            model_space = drawing.modelspace()

            shape = self._build_shape(params)
            selector = self._get_selector(params.selection_rule)

            handles = [
                str(getattr(entity.dxf, "handle", ""))
                for entity in selector(shape, model_space)
            ]
            handles = [handle.strip().lower() for handle in handles if handle]
            return Result.success(handles)
        except Exception as e:
            return Result.fail(
                f"EzdxfAreaSelector failed: file='{filepath}', shape={params.shape_type.value}, "
                f"rule={params.selection_rule.value}, args_count={len(params.shape_args)}, error={e}"
            )

    def _build_shape(self, params: AreaSelectionParams):
        shape_args = params.shape_args

        if params.shape_type == ShapeType.RECTANGLE:
            if len(shape_args) != 4:
                raise ValueError("Rectangle requires x_min, x_max, y_min, y_max")
            x_min, x_max, y_min, y_max = shape_args
            return select.Window((float(x_min), float(y_min)), (float(x_max), float(y_max)))

        if params.shape_type == ShapeType.CIRCLE:
            if len(shape_args) != 2:
                raise ValueError("Circle requires center_point and radius")

            center_point, radius = shape_args
            if hasattr(center_point, "x") and hasattr(center_point, "y"):
                center = (float(center_point.x()), float(center_point.y()))
            else:
                center = center_point

            return select.Circle(center, float(radius))

        if params.shape_type == ShapeType.POLYGON:
            if len(shape_args) != 1:
                raise ValueError("Polygon requires sequence of points")
            points = shape_args[0]
            return select.Polygon(points)

        raise ValueError(f"Unsupported shape type: {params.shape_type}")

    def _get_selector(self, selection_rule: SelectionRule):
        selectors = {
            SelectionRule.INSIDE: select.bbox_inside,
            SelectionRule.OUTSIDE: select.bbox_outside,
            SelectionRule.INTERSECT: select.bbox_overlap,
        }

        if selection_rule not in selectors:
            raise ValueError(f"Unsupported selection rule: {selection_rule}")

        return selectors[selection_rule]
