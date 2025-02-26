from .BaseMapTool import BaseMapTool
from qgis.gui import QgsRubberBand
from PyQt5 import QtGui, QtCore
from qgis.core import QgsWkbTypes

class PolygonMapTool(BaseMapTool):
    def __init__(self, canvas, dlg):
        super().__init__(canvas, dlg)
        self.tempRubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.tempRubberBand.setColor(QtGui.QColor(0, 0, 255, 100))
        self.tempRubberBand.setWidth(1)
        self.reset()

    def reset(self):
        super().reset()
        self.points = []
        self.tempRubberBand.reset(QgsWkbTypes.LineGeometry)
    
    def canvasPressEvent(self, e):
        point = self.toMapCoordinates(e.pos())
        self.points.append(point)
        self.rubberBand.addPoint(point, False)
        self.rubberBand.show()
        if not self.isEmittingPoint:
            self.isEmittingPoint = True
        else:
            self.tempRubberBand.addPoint(point, True)
    
    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint or not self.points:
            return
        point = self.toMapCoordinates(e.pos())
        self.tempRubberBand.reset(QgsWkbTypes.LineGeometry)
        self.tempRubberBand.addPoint(self.points[-1], False)
        self.tempRubberBand.addPoint(point, True)
        self.showTemporaryPolygon(point)
    
    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Return and len(self.points) > 2:
            self.completePolygon()

    def canvasDoubleClickEvent(self, e):
        if len(self.points) > 2:
            self.completePolygon()

    def completePolygon(self):
        self.rubberBand.closePoints()
        self.rubberBand.show()
        self.tempRubberBand.reset(QgsWkbTypes.LineGeometry)
        self.geom = [(point.x(), point.y()) for point in self.points]
        
        coords_str = ", ".join([f"({x:.2f}, {y:.2f})" for x, y in self.geom])
        
        self.dlg.start_long_task("select_entities_in_area", self.dlg.dxf_handler.select_entities_in_area, self.geom)
        self.update_dialog_coordinates(
            self.dlg.lm.get_string("DRAW", "polygon_coordinates", coords_str)
        )
        self.finish_drawing()
        
    def showTemporaryPolygon(self, point):
        if not self.points:
            return
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        for p in self.points:
            self.rubberBand.addPoint(p, False)
        self.rubberBand.addPoint(point, True)
        self.rubberBand.show()