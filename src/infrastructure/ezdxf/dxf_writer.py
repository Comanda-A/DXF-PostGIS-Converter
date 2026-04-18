import os

import ezdxf

from ...domain.entities import DXFDocument
from ...domain.services import IDXFWriter
from ...domain.value_objects import Result, Unit


class DXFWriter(IDXFWriter):
	"""Инфраструктурный адаптер для операций записи DXF через ezdxf."""

	def save(self, document: DXFDocument, filepath: str) -> Result[Unit]:
		if not document.filepath:
			return Result.fail("Source file path is empty")

		# Текущая реализация сохраняет исходный DXF без изменений.
		return self.save_selected_by_handles(document.filepath, filepath, set())

	def save_selected_by_handles(
		self,
		source_filepath: str,
		output_path: str,
		selected_handles: set[str],
	) -> Result[int]:
		try:
			drawing = ezdxf.readfile(source_filepath)
			modelspace = drawing.modelspace()

			normalized_handles = {h.strip().upper() for h in selected_handles if h.strip()}

			removed_count = 0
			for dxf_entity in list(modelspace):
				handle = str(getattr(dxf_entity.dxf, "handle", "")).strip().upper()
				if normalized_handles and handle not in normalized_handles:
					modelspace.delete_entity(dxf_entity)
					removed_count += 1

			output_dir = os.path.dirname(output_path)
			if output_dir:
				os.makedirs(output_dir, exist_ok=True)

			drawing.saveas(output_path)
			return Result.success(removed_count)

		except Exception as exc:
			return Result.fail(f"Failed to save DXF file: {str(exc)}")
