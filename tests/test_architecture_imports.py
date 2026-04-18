# -*- coding: utf-8 -*-
"""Архитектурные проверки импортов между слоями."""

from __future__ import annotations

import ast
import os
import unittest
from pathlib import Path


class TestArchitectureImports(unittest.TestCase):
    """Проверяет, что зависимости направлены только внутрь архитектуры."""

    @classmethod
    def setUpClass(cls):
        cls.project_root = Path(__file__).resolve().parents[1]
        cls.src_root = cls.project_root / "src"
        cls.ezdxf_infra_dir = cls.src_root / "infrastructure" / "ezdxf"

    def _iter_python_files(self):
        for file_path in self.src_root.rglob("*.py"):
            yield file_path

    def _iter_import_targets(self, tree: ast.AST):
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield alias.name, node.lineno
            elif isinstance(node, ast.ImportFrom):
                base = "." * node.level + (node.module or "")
                if base:
                    yield base, node.lineno
                elif node.names:
                    for alias in node.names:
                        yield alias.name, node.lineno

    @staticmethod
    def _has_segment(target: str, segment: str) -> bool:
        normalized = target.strip(".")
        if not normalized:
            return False
        return segment in normalized.split(".")

    def _collect_violations(self):
        violations: list[str] = []

        for file_path in self._iter_python_files():
            rel_path = file_path.relative_to(self.project_root).as_posix()
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))

            for target, lineno in self._iter_import_targets(tree):
                # 1) Domain не должен зависеть от внешних внутренних слоев.
                if "/src/domain/" in f"/{rel_path}/":
                    if self._has_segment(target, "application") or self._has_segment(target, "infrastructure") or self._has_segment(target, "presentation"):
                        violations.append(f"{rel_path}:{lineno} -> domain импортирует '{target}'")

                # 2) Application не должен зависеть от infrastructure/presentation.
                if "/src/application/" in f"/{rel_path}/":
                    if self._has_segment(target, "infrastructure") or self._has_segment(target, "presentation"):
                        violations.append(f"{rel_path}:{lineno} -> application импортирует '{target}'")

                # 3) Presentation должен идти через application-слой.
                if "/src/presentation/" in f"/{rel_path}/":
                    if self._has_segment(target, "domain") or self._has_segment(target, "infrastructure"):
                        violations.append(f"{rel_path}:{lineno} -> presentation импортирует '{target}'")

                # 4) Прямой импорт библиотеки ezdxf допускается только в infra/ezdxf.
                is_ezdxf_import = target == "ezdxf" or target.startswith("ezdxf.")
                if is_ezdxf_import and not file_path.is_relative_to(self.ezdxf_infra_dir):
                    violations.append(f"{rel_path}:{lineno} -> прямой импорт '{target}' вне infrastructure/ezdxf")

        return violations

    def test_layer_boundaries(self):
        violations = self._collect_violations()
        if violations:
            message = "\n".join(["Найдены архитектурные утечки импортов:"] + violations)
            self.fail(message)


if __name__ == "__main__":
    unittest.main()
