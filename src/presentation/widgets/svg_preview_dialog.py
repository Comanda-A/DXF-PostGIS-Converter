from __future__ import annotations

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QPainter
from qgis.PyQt.QtSvg import QGraphicsSvgItem, QSvgRenderer
from qgis.PyQt.QtWidgets import (
    QDialog,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
)


class _ZoomPanGraphicsView(QGraphicsView):
    """Graphics view with wheel zoom and LMB pan."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._zoom_step = 1.15
        self._current_zoom = 1.0

        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

    def wheelEvent(self, event):
        factor = self._zoom_step if event.angleDelta().y() > 0 else (1.0 / self._zoom_step)
        self.scale(factor, factor)
        self._current_zoom *= factor

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)


class SvgPreviewDialog(QDialog):
    """Simple SVG preview dialog with zoom controls."""

    def __init__(self, svg_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DXF Preview")
        self.resize(900, 700)
        self._initial_fit_done = False

        self._scene = QGraphicsScene(self)
        self._renderer = QSvgRenderer(svg_path)
        self._svg_item = QGraphicsSvgItem()
        self._svg_item.setSharedRenderer(self._renderer)
        self._scene.addItem(self._svg_item)

        bounds = self._scene.itemsBoundingRect()
        if bounds.isValid() and not bounds.isEmpty():
            self._scene.setSceneRect(bounds)

        self._view = _ZoomPanGraphicsView(self)
        self._view.setScene(self._scene)
        self._view.setCursor(Qt.OpenHandCursor)

        root_layout = QVBoxLayout(self)
        root_layout.addWidget(self._view)

        buttons_layout = QHBoxLayout()
        reset_button = QPushButton("Reset")
        zoom_in_button = QPushButton("Zoom In")
        zoom_out_button = QPushButton("Zoom Out")
        close_button = QPushButton("Close")

        reset_button.clicked.connect(self._reset_view)
        zoom_in_button.clicked.connect(lambda: self._zoom(1.2))
        zoom_out_button.clicked.connect(lambda: self._zoom(0.8))
        close_button.clicked.connect(self.accept)

        buttons_layout.addWidget(reset_button)
        buttons_layout.addWidget(zoom_in_button)
        buttons_layout.addWidget(zoom_out_button)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(close_button)

        root_layout.addLayout(buttons_layout)
        self._reset_view()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_fit_done:
            self._initial_fit_done = True
            # Выполняем fit после реального layout окна, чтобы открыть в размер viewport.
            QTimer.singleShot(0, self._reset_view)

    def _reset_view(self) -> None:
        self._view.resetTransform()
        self._view._current_zoom = 1.0
        target = self._scene.itemsBoundingRect()
        if target.isValid() and not target.isEmpty():
            self._view.fitInView(target, Qt.KeepAspectRatio)

    def _zoom(self, factor: float) -> None:
        self._view.scale(factor, factor)
        self._view._current_zoom *= factor
