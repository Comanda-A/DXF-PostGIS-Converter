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

			temp_doc = ezdxf.new()
			temp_modelspace = temp_doc.modelspace()

			# Restore layer table attributes so ByLayer entities keep original visual styles.
			layer_definitions = self._collect_layer_definitions_from_entities(entities)
			report_lines.append(f"Layer definitions collected: {len(layer_definitions)}")
			for layer_name, layer_attribs in layer_definitions.items():
				try:
					if layer_name in temp_doc.layers:
						layer = temp_doc.layers.get(layer_name)
						for key, value in layer_attribs.items():
							try:
								setattr(layer.dxf, key, value)
							except Exception:
								pass
					else:
						temp_doc.layers.new(name=layer_name, dxfattribs=layer_attribs)
				except Exception:
					continue

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
					if dxftype == "ATTRIB":
						attrib_text = (entity.geometries or {}).get("text") or (entity.attributes or {}).get("text") or ""
						text_attribs = dict(attribs)
						text_attribs["text"] = attrib_text
						for color_key in ("color", "true_color", "transparency"):
							if color_key not in text_attribs and (entity.geometries or {}).get(color_key) is not None:
								text_attribs[color_key] = (entity.geometries or {}).get(color_key)
						text_entity = ezdxf_factory.new("TEXT", dxfattribs=self._clean_ezdxf_attribs(text_attribs, "TEXT"))
						self._apply_geometry_dict(text_entity, entity.geometries or {}, "TEXT")
						ez_entity = text_entity
					elif dxftype == "MULTILEADER":
						ez_entity = self._build_multileader(temp_modelspace, entity)
					elif dxftype == "LEADER":
						ez_entity = ezdxf_factory.new(dxftype, dxfattribs=attribs)
						self._apply_entity_geometry(ez_entity, entity, dxftype)
					else:
						ez_entity = ezdxf_factory.new(dxftype, dxfattribs=attribs)
						self._apply_entity_geometry(ez_entity, entity, dxftype)
					if ez_entity is not None:
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
		if dxftype == "POINT":
			location = geometry.get("location")
			if location:
				try:
					ez_entity.dxf.location = location
				except Exception:
					pass

		elif dxftype == "LINE":
			start = geometry.get("start")
			end = geometry.get("end")
			if start:
				try:
					ez_entity.dxf.start = start
				except Exception:
					pass
			if end:
				try:
					ez_entity.dxf.end = end
				except Exception:
					pass

		elif dxftype == "TEXT":
			insert = geometry.get("insert")
			if insert:
				try:
					ez_entity.dxf.insert = insert
				except Exception:
					pass
			for key in ("color", "true_color", "transparency"):
				if key in geometry and geometry.get(key) is not None:
					try:
						setattr(ez_entity.dxf, key, geometry.get(key))
					except Exception:
						pass
			for key in ("text", "height", "rotation", "oblique", "style", "halign", "valign"):
				if key in geometry and geometry.get(key) is not None:
					try:
						setattr(ez_entity.dxf, key, geometry.get(key))
					except Exception:
						pass

		elif dxftype == "MTEXT":
			insert = geometry.get("insert")
			if insert:
				try:
					ez_entity.dxf.insert = insert
				except Exception:
					pass
			for key in ("color", "true_color", "transparency"):
				if key in geometry and geometry.get(key) is not None:
					try:
						setattr(ez_entity.dxf, key, geometry.get(key))
					except Exception:
						pass
			if geometry.get("text") is not None:
				try:
					ez_entity.text = geometry.get("text")
				except Exception:
					pass
			for key in ("height", "rotation"):
				if key in geometry and geometry.get(key) is not None:
					try:
						setattr(ez_entity.dxf, key if key != "height" else "char_height", geometry.get(key))
					except Exception:
						pass

		elif dxftype == "INSERT":
			insert = geometry.get("insert")
			if insert:
				try:
					ez_entity.dxf.insert = insert
				except Exception:
					pass
			for key in ("name", "xscale", "yscale", "zscale", "rotation"):
				if key in geometry and geometry.get(key) is not None:
					try:
						setattr(ez_entity.dxf, key, geometry.get(key))
					except Exception:
						pass

			for attrib_payload in (geometry.get("insert_attribs") or []):
				try:
					tag = str(attrib_payload.get("tag") or "")
					text = str(attrib_payload.get("text") or "")
					insert_point = attrib_payload.get("insert") or insert or (0.0, 0.0, 0.0)
					dxfattribs = {}
					for key in ("height", "rotation", "style", "layer", "color", "true_color", "transparency"):
						value = attrib_payload.get(key)
						if value is not None:
							dxfattribs[key] = value

					ez_entity.add_attrib(
						tag,
						text,
						insert=insert_point,
						dxfattribs=dxfattribs or None,
					)
				except Exception:
					pass

		elif dxftype == "CIRCLE":
			center = geometry.get("center")
			if center:
				try:
					ez_entity.dxf.center = center
				except Exception:
					pass
			radius = geometry.get("radius")
			if radius is not None:
				try:
					ez_entity.dxf.radius = radius
				except Exception:
					pass

		elif dxftype == "ARC":
			center = geometry.get("center")
			if center:
				try:
					ez_entity.dxf.center = center
				except Exception:
					pass
			for key in ("radius", "start_angle", "end_angle"):
				if key in geometry and geometry.get(key) is not None:
					try:
						setattr(ez_entity.dxf, key, geometry.get(key))
					except Exception:
						pass

		elif dxftype == "ELLIPSE":
			for key in ("center", "major_axis", "ratio", "start_param", "end_param", "extrusion"):
				if key in geometry and geometry.get(key) is not None:
					try:
						setattr(ez_entity.dxf, key, geometry.get(key))
					except Exception:
						pass

		elif dxftype == "POLYLINE":
			points = geometry.get("points") or []
			if points:
				try:
					for point in points:
						ez_entity.append_vertex(point)
				except Exception:
					pass
			if "is_closed" in geometry:
				try:
					ez_entity.closed = bool(geometry.get("is_closed"))
				except Exception:
					pass

		elif dxftype == "LWPOLYLINE":
			points = geometry.get("points") or []
			if points:
				try:
					ez_entity.append_points(points, format="xyseb")
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

		elif dxftype == "3DFACE":
			for key in ("vtx0", "vtx1", "vtx2", "vtx3"):
				if key in geometry and geometry.get(key) is not None:
					try:
						setattr(ez_entity.dxf, key, geometry.get(key))
					except Exception:
						pass

		elif dxftype in {"SOLID", "TRACE"}:
			for key in ("vtx0", "vtx1", "vtx2", "vtx3"):
				if key in geometry and geometry.get(key) is not None:
					try:
						setattr(ez_entity.dxf, key, geometry.get(key))
					except Exception:
						pass

		elif dxftype == "RAY" or dxftype == "XLINE":
			for key in ("start", "unit_vector"):
				if key in geometry and geometry.get(key) is not None:
					try:
						setattr(ez_entity.dxf, key, geometry.get(key))
					except Exception:
						pass

		elif dxftype == "VIEWPORT":
			for key in ("center", "width", "height"):
				if key in geometry and geometry.get(key) is not None:
					try:
						setattr(ez_entity.dxf, key, geometry.get(key))
					except Exception:
						pass

		elif dxftype == "LEADER":
			vertices = geometry.get("vertices") or []
			if vertices:
				try:
					ez_entity.set_vertices(vertices)
				except Exception:
					pass
			if geometry.get("text") is not None:
				try:
					ez_entity.dxf.text = geometry.get("text")
				except Exception:
					pass

		elif dxftype == "HATCH":
			try:
				if geometry.get("solid_fill"):
					try:
						ez_entity.dxf.solid_fill = 1
					except Exception:
						pass

				pattern_name = geometry.get("pattern_name") or "SOLID"
				try:
					ez_entity.dxf.pattern_name = pattern_name
				except Exception:
					pass

				hatch_paths = geometry.get("hatch_paths") or []
				if hatch_paths:
					for path in hatch_paths:
						path_type = str(path.get("path_type") or "").lower()
						if path_type == "polyline":
							vertices = []
							for vertex in (path.get("vertices") or []):
								if isinstance(vertex, (list, tuple)) and len(vertex) >= 3:
									vertices.append((float(vertex[0]), float(vertex[1]), float(vertex[2])))
								elif isinstance(vertex, (list, tuple)) and len(vertex) >= 2:
									vertices.append((float(vertex[0]), float(vertex[1])))

							if len(vertices) >= 2:
								ez_entity.paths.add_polyline_path(
									vertices,
									is_closed=bool(path.get("is_closed", True)),
								)

						elif path_type == "edge":
							edge_path = ez_entity.paths.add_edge_path()
							for edge in (path.get("edges") or []):
								edge_type = str(edge.get("edge_type") or "").lower()
								if edge_type == "line":
									start = edge.get("start") or []
									end = edge.get("end") or []
									if len(start) >= 2 and len(end) >= 2:
										edge_path.add_line((float(start[0]), float(start[1])), (float(end[0]), float(end[1])))
								elif edge_type == "arc":
									center = edge.get("center") or []
									radius = edge.get("radius")
									start_angle = edge.get("start_angle")
									end_angle = edge.get("end_angle")
									if len(center) >= 2 and radius is not None and start_angle is not None and end_angle is not None:
										edge_path.add_arc(
											(float(center[0]), float(center[1])),
											float(radius),
											float(start_angle),
											float(end_angle),
											ccw=bool(edge.get("ccw", True)),
										)
				else:
					boundaries = geometry.get("boundaries") or []
					for boundary in boundaries:
						points_2d = [(float(point[0]), float(point[1])) for point in boundary if len(point) >= 2]
						if len(points_2d) >= 2:
							ez_entity.paths.add_polyline_path(points_2d, is_closed=True)
			except Exception:
				pass

	def _build_multileader(self, temp_modelspace, entity: DXFEntity):
		"""Build a visual MULTILEADER using the ezdxf builder API."""
		from ezdxf.math import Vec2

		geometry = entity.geometries or {}
		leader_lines = geometry.get("leader_lines") or []
		text = geometry.get("text") or (entity.attributes or {}).get("text") or ""
		char_height = geometry.get("char_height")

		first_line = leader_lines[0] if leader_lines else []
		if len(first_line) >= 2:
			target_raw = first_line[-1]
			prev_raw = first_line[-2]
		else:
			target_raw = geometry.get("base_point") or [0.0, 0.0, 0.0]
			prev_raw = [float(target_raw[0]) - 20.0, float(target_raw[1]), float(target_raw[2] if len(target_raw) > 2 else 0.0)]

		target = Vec2(float(target_raw[0]), float(target_raw[1]))
		segment1 = Vec2(float(prev_raw[0]) - float(target_raw[0]), float(prev_raw[1]) - float(target_raw[1]))

		builder = temp_modelspace.add_multileader_mtext("Standard")
		try:
			if char_height is not None:
				builder.set_content(text, char_height=char_height)
			else:
				builder.set_content(text)
		except Exception:
			pass

		try:
			builder.quick_leader(text, target=target, segment1=segment1)
		except Exception:
			pass

		try:
			return builder.build(insert=target)
		except Exception:
			return None

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

	def _collect_layer_definitions_from_entities(self, entities: Sequence[DXFEntity]) -> dict[str, dict]:
		layer_defs: dict[str, dict] = {}
		for entity in entities:
			extra_data = entity.extra_data or {}
			layer_name = str(
				extra_data.get("layer_name")
				or (entity.attributes or {}).get("layer")
				or (extra_data.get("dxf_attribs", {}) or {}).get("layer")
				or ""
			).strip()
			if not layer_name:
				continue

			raw_layer_attribs = dict(extra_data.get("layer_dxf_attribs", {}) or {})
			if not raw_layer_attribs:
				continue

			layer_attribs = self._clean_ezdxf_attribs(raw_layer_attribs, "LAYER")
			if layer_attribs:
				layer_defs[layer_name] = layer_attribs

		return layer_defs

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
