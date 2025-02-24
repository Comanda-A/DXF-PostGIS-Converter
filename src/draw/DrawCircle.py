import math
from .BaseMapTool import BaseMapTool
from qgis.core import QgsWkbTypes, QgsPointXY

class CircleMapTool(BaseMapTool):
    def __init__(self, canvas, dlg):
        super().__init__(canvas, dlg)
        self.reset()
    
    def reset(self):
        super().reset()
        self.centerPoint = None
        self.radiusPoint = None
    
    def canvasPressEvent(self, e):
        self.centerPoint = self.toMapCoordinates(e.pos())
        self.radiusPoint = self.centerPoint
        self.isEmittingPoint = True
        self.showCircle(self.centerPoint, self.radiusPoint)
    
    def canvasReleaseEvent(self, e):
        self.isEmittingPoint = False
        radius = self.calculateRadius()
        if radius is not None:
            self.radius = radius
            self.dlg.start_long_task("select_entities_in_area", self.dlg.dxf_handler.select_entities_in_area, 
                                   None, self.centerPoint, self.radius)
            self.update_dialog_coordinates(f"Координаты круга:\n Центр :{self.centerPoint}\nРадиус:{self.radius}")
            self.finish_drawing()

    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return
        self.radiusPoint = self.toMapCoordinates(e.pos())
        self.showCircle(self.centerPoint, self.radiusPoint)
    
    def showCircle(self, centerPoint, radiusPoint):
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        radius = centerPoint.distance(radiusPoint)
        
        num_segments = 100
        points = [
            QgsPointXY(
                centerPoint.x() + radius * math.cos(i * (2 * math.pi / num_segments)),
                centerPoint.y() + radius * math.sin(i * (2 * math.pi / num_segments))
            )
            for i in range(num_segments + 1)
        ]
        
        for i, point in enumerate(points):
            self.rubberBand.addPoint(point, i == len(points)-1)
        
        self.rubberBand.show()

    def calculateRadius(self):
        if self.centerPoint is None or self.radiusPoint is None:
            return None
        return self.centerPoint.distance(self.radiusPoint)
