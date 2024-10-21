from qgis.gui import QgsRubberBand, QgsMapToolEmitPoint, QgsMapTool
from PyQt5 import QtGui, QtCore
from qgis.core import QgsWkbTypes, QgsPointXY, QgsGeometry, QgsFeatureRequest

class PolygonMapTool(QgsMapToolEmitPoint):
    def __init__(self, canvas, dlg):
        self.canvas = canvas
        QgsMapToolEmitPoint.__init__(self, self.canvas)
        self.rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubberBand.setColor(QtGui.QColor(0, 0, 255))
        self.rubberBand.setFillColor(QtGui.QColor(0, 0, 255, 50))
        self.rubberBand.setWidth(1)
        self.tempRubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.tempRubberBand.setColor(QtGui.QColor(0, 0, 255, 100))
        self.tempRubberBand.setWidth(1)
        self.reset()
        self.dlg = dlg

    def reset(self):
        self.points = []
        self.isEmittingPoint = False
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
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

    
    def canvasReleaseEvent(self, e):
        pass
    
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
        self.dlg.start_long_task("select_entities_in_area", self.dlg.dxf_handler.select_entities_in_area, self.dlg.dxf_handler, self.geom)
        self.dlg.coord.setPlainText(f"Координаты полигона:\n {self.geom}")
        
        self.deactivate()
        self.canvas.unsetMapTool(self)
        self.canvas.refresh()
        self.dlg.showNormal()
        self.reset()
        
    def showTemporaryPolygon(self, point):
        if not self.points:
            return
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        for p in self.points:
            self.rubberBand.addPoint(p, False)
        self.rubberBand.addPoint(point, True)
        self.rubberBand.show()
    def deactivate(self):
        QgsMapTool.deactivate(self)
        self.deactivated.emit()