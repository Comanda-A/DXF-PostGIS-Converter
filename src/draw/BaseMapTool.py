from qgis.gui import QgsRubberBand, QgsMapToolEmitPoint, QgsMapTool
from PyQt5 import QtGui
from qgis.core import QgsWkbTypes

class BaseMapTool(QgsMapToolEmitPoint):
    def __init__(self, canvas, dlg, geometry_type=QgsWkbTypes.PolygonGeometry):
        self.canvas = canvas
        QgsMapToolEmitPoint.__init__(self, self.canvas)
        self.rubberBand = QgsRubberBand(self.canvas, geometry_type)
        self.rubberBand.setColor(QtGui.QColor(0, 0, 255))
        self.rubberBand.setFillColor(QtGui.QColor(0, 0, 255, 50))
        self.rubberBand.setWidth(1)
        self.dlg = dlg
        self.isEmittingPoint = False

    def reset(self):
        self.isEmittingPoint = False
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)

    def finish_drawing(self):
        self.deactivate()
        self.canvas.unsetMapTool(self)
        self.canvas.refresh()
        self.dlg.showNormal()
        self.reset()

    def deactivate(self):
        QgsMapTool.deactivate(self)
        self.deactivated.emit()

    def update_dialog_coordinates(self, coord_text):
        self.dlg.show()
        self.dlg.coord.setPlainText(coord_text)
