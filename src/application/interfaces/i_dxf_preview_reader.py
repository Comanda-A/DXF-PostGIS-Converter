from __future__ import annotations

from abc import ABC, abstractmethod


class IDXFPreviewReader(ABC):
    """Прикладной контракт генерации SVG-превью DXF."""

    @abstractmethod
    def save_svg_preview(
        self,
        filepath: str,
        output_dir: str,
        filename: str = "",
    ):
        """Возвращает объект результата с полями is_fail/error/value."""
        pass
