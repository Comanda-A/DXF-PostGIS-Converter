from __future__ import annotations

import os
import tempfile
from typing import Sequence

import ezdxf

from ...domain.entities import DXFDocument, DXFEntity
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

	def reconstruct_from_entities(self, entities: Sequence[DXFEntity]) -> Result[tuple[bytes, str]]:
		try:
			report_lines: list[str] = []
			report_lines.append(f"Reconstruction started for {len(entities)} entity(ies)")

			dxf_entities_to_write = []
			skipped_entities = 0
			reconstructed_by_type: dict[str, int] = {}

			from ezdxf.entities import factory as ezdxf_factory

			for entity in entities:
				dxftype = self._resolve_entity_dxftype(entity)
				entity_name = self._resolve_entity_name(entity)
				if not dxftype:
					skipped_entities += 1
					report_lines.append(
						f"skipped entity id={getattr(entity, 'id', None)}, name='{entity_name}' because dxftype could not be resolved"
					)
					continue

				attribs = self._build_ezdxf_attribs(entity, dxftype)
				try:
					ez_entity = ezdxf_factory.new(dxftype, dxfattribs=attribs)
					self._apply_entity_geometry(ez_entity, entity, dxftype)
					dxf_entities_to_write.append(ez_entity)
					reconstructed_by_type[dxftype] = reconstructed_by_type.get(dxftype, 0) + 1
					report_lines.append(
						f"ok entity id={getattr(entity, 'id', None)}, name='{entity_name}', dxftype={dxftype}, attr_keys={sorted(list(attribs.keys()))[:12]}, geom_keys={sorted(list((entity.geometries or {}).keys()))[:12]}"
					)
				except Exception as exc:
					skipped_entities += 1
					report_lines.append(
						f"FAILED entity id={getattr(entity, 'id', None)}, name='{entity_name}', dxftype={dxftype}, error={type(exc).__name__}: {exc}, attr_keys={sorted(list(attribs.keys()))[:12]}, geom_keys={sorted(list((entity.geometries or {}).keys()))[:12]}"
					)

			if not dxf_entities_to_write:
				report_lines.append(
					f"Reconstruction summary: reconstructed=0, skipped={skipped_entities}, by_type={reconstructed_by_type}"
				)
				return Result.fail("\n".join(report_lines))

			report_lines.append(
				f"Reconstruction summary: reconstructed={len(dxf_entities_to_write)}, skipped={skipped_entities}, by_type={reconstructed_by_type}"
			)

			temp_doc = ezdxf.new()
			temp_modelspace = temp_doc.modelspace()

			# Build all block definitions recursively from serialized payloads.
			block_definitions = self._collect_block_definitions_from_entities(entities)
			report_lines.append(f"Block definitions collected: {len(block_definitions)}")

			from ezdxf.entities import factory as ezdxf_factory
			for block_name in block_definitions.keys():
				try:
					temp_doc.blocks.new(name=block_name)
				except Exception:
					# block may already exist or have invalid name; continue and attempt to fill if possible
					pass

			for block_name, block_entities in block_definitions.items():
				try:
					block_layout = temp_doc.blocks.get(block_name)
				except Exception:
					continue

				for block_entity in block_entities:
					try:
						b_dxftype = str(block_entity.get("dxftype", "")).upper()
						if not b_dxftype:
							continue

						b_attribs = dict(block_entity.get("dxf_attribs", {}) or {})
						b_attribs.update(block_entity.get("attributes", {}) or {})
						b_attribs = self._clean_ezdxf_attribs(b_attribs, b_dxftype)

						b_ez_entity = ezdxf_factory.new(b_dxftype, dxfattribs=b_attribs)
						self._apply_geometry_dict(b_ez_entity, block_entity.get("geometries", {}) or {}, b_dxftype)
						block_layout.add_entity(b_ez_entity)
					except Exception:
						continue

			# add modelspace entities after blocks are defined
			for ez_entity in dxf_entities_to_write:
				temp_modelspace.add_entity(ez_entity)

			with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as temp_file:
				tmp_path = temp_file.name

			try:
				temp_doc.saveas(tmp_path)
				with open(tmp_path, "rb") as file_handle:
					data = file_handle.read()
			finally:
				try:
					os.remove(tmp_path)
				except OSError:
					pass

			return Result.success((data, "\n".join(report_lines)))
		except Exception as exc:
			return Result.fail(f"Table reconstruction failed: {type(exc).__name__}: {str(exc)}")

	def _build_ezdxf_attribs(self, entity: DXFEntity, dxftype: str) -> dict:
		attribs = dict((entity.extra_data or {}).get("dxf_attribs", {}))
		attribs.update(entity.attributes or {})
		return self._clean_ezdxf_attribs(attribs, dxftype)

	def _clean_ezdxf_attribs(self, attribs: dict, dxftype: str) -> dict:
		"""Remove attributes that should not be written directly into a newly created entity."""

		ignore_keys = {"points", "is_closed", "location", "start", "end"} if dxftype == "LWPOLYLINE" else set()

		cleaned: dict = {}
		for key, value in attribs.items():
			if key in {"handle", "owner_handle", "paperspace"}:
				continue
			if key in ignore_keys:
				continue
			if value is None:
				continue
			if isinstance(value, str) and value.strip().lower() in {"none", "null", ""}:
				continue
			cleaned[key] = value

		return cleaned

	def _apply_entity_geometry(self, ez_entity, entity: DXFEntity, dxftype: str) -> None:
		geometry = entity.geometries or {}
		self._apply_geometry_dict(ez_entity, geometry, dxftype)

	def _apply_geometry_dict(self, ez_entity, geometry: dict, dxftype: str) -> None:

		if dxftype == "LWPOLYLINE":
			points = geometry.get("points") or []
			if points:
				try:
					ez_entity.append_points(points)
				except Exception:
					pass

			if "is_closed" in geometry:
				try:
					ez_entity.closed = bool(geometry.get("is_closed"))
				except Exception:
					pass

			if "elevation" in geometry and geometry.get("elevation") is not None:
				try:
					ez_entity.dxf.elevation = geometry.get("elevation")
				except Exception:
					pass

			if "const_width" in geometry and geometry.get("const_width") is not None:
				try:
					ez_entity.dxf.const_width = geometry.get("const_width")
				except Exception:
					pass

	def _collect_block_definitions_from_entities(self, entities: Sequence[DXFEntity]) -> dict[str, list[dict]]:
		block_defs: dict[str, list[dict]] = {}
		for entity in entities:
			extra_data = entity.extra_data or {}
			block_name = extra_data.get("block_name")
			block_entities = extra_data.get("block_entities")
			if block_name and isinstance(block_entities, list):
				self._collect_block_definition_recursive(block_name, block_entities, block_defs)

			# Fallback: ensure every INSERT target name has at least a placeholder definition.
			dxftype = str(extra_data.get("dxftype") or getattr(getattr(entity, "entity_type", None), "value", "")).upper()
			if dxftype == "INSERT":
				insert_name = (
					(entity.attributes or {}).get("name")
					or (extra_data.get("dxf_attribs", {}) or {}).get("name")
					or (entity.geometries or {}).get("name")
				)
				if insert_name and insert_name not in block_defs:
					block_defs[str(insert_name)] = []
		return block_defs

	def _collect_block_definition_recursive(self, block_name: str, block_entities: list[dict], block_defs: dict[str, list[dict]]) -> None:
		if block_name not in block_defs:
			block_defs[block_name] = block_entities

		for block_entity in block_entities:
			nested_name = block_entity.get("block_name")
			nested_entities = block_entity.get("block_entities")
			if nested_name and isinstance(nested_entities, list):
				self._collect_block_definition_recursive(nested_name, nested_entities, block_defs)

	def _resolve_entity_dxftype(self, entity: DXFEntity) -> str:
		extra_data = entity.extra_data or {}
		dxftype = extra_data.get("dxftype")
		if dxftype:
			return str(dxftype).upper()

		entity_type = getattr(entity, "entity_type", None)
		if entity_type is None:
			return ""

		type_value = getattr(entity_type, "value", entity_type)
		if not type_value:
			return ""

		return str(type_value).upper()

	def _resolve_entity_name(self, entity: DXFEntity) -> str:
		attributes = entity.attributes or {}
		if attributes.get("name"):
			return str(attributes.get("name"))

		extra_data = entity.extra_data or {}
		dxf_attribs = extra_data.get("dxf_attribs", {}) or {}
		if dxf_attribs.get("name"):
			return str(dxf_attribs.get("name"))

		return str(getattr(entity, "name", ""))
