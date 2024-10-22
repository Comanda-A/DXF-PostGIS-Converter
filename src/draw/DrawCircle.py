import math
import asyncio
from qgis.gui import QgsRubberBand, QgsMapToolEmitPoint, QgsMapTool
from PyQt5 import QtGui
from qgis.core import QgsWkbTypes, QgsPointXY

class CircleMapTool(QgsMapToolEmitPoint):
    def __init__(self, canvas, dlg):
        self.canvas = canvas
        QgsMapToolEmitPoint.__init__(self, self.canvas)
        self.rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubberBand.setColor(QtGui.QColor(0, 0, 255))
        self.rubberBand.setFillColor(QtGui.QColor(0, 0, 255, 50))
        self.rubberBand.setWidth(1)
        self.reset()
        self.dlg = dlg
    
    def reset(self):
        self.centerPoint = None
        self.radiusPoint = None
        self.isEmittingPoint = False
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
    
    def canvasPressEvent(self, e):
        self.centerPoint = self.toMapCoordinates(e.pos())
        self.radiusPoint = self.centerPoint
        self.isEmittingPoint = True
        self.showCircle(self.centerPoint, self.radiusPoint)
    
    def canvasReleaseEvent(self, e):
        self.isEmittingPoint = False
        radius = self.calculateRadius()
        if radius is not None:
            self.deactivate()
            self.canvas.unsetMapTool(self)
            self.canvas.refresh()
            self.dlg.showNormal()
            
            self.radius = radius
                
            self.dlg.show()
            asyncio.run(self.dlg.start_long_task("select_entities_in_area", self.dlg.dxf_handler.select_entities_in_area, None, self.centerPoint, self.radius))
            self.dlg.coord.setPlainText(f"Координаты круга:\n Центр :{self.centerPoint}\nРадиус:{self.radius}")
            self.reset()

    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return
    
        self.radiusPoint = self.toMapCoordinates(e.pos())
        self.showCircle(self.centerPoint, self.radiusPoint)
    
    def showCircle(self, centerPoint, radiusPoint):
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        radius = centerPoint.distance(radiusPoint)
        
        points = []
        num_segments = 100
        for i in range(num_segments):
            angle = i * (2 * math.pi / num_segments)
            x = centerPoint.x() + radius * math.cos(angle)
            y = centerPoint.y() + radius * math.sin(angle)
            points.append(QgsPointXY(x, y))
        
        for point in points:
            self.rubberBand.addPoint(point, False)
        self.rubberBand.addPoint(points[0], True)
        self.rubberBand.show()

    def calculateRadius(self):
        if self.centerPoint is None or self.radiusPoint is None:
            return None
        return self.centerPoint.distance(self.radiusPoint)
    
    def deactivate(self):
        QgsMapTool.deactivate(self)
        self.deactivated.emit()
