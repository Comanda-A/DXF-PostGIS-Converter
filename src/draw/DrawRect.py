from qgis.gui import QgsRubberBand, QgsMapToolEmitPoint, QgsMapTool
from PyQt5 import QtGui
from qgis.core import QgsWkbTypes, QgsRectangle, QgsPointXY
from .BaseMapTool import BaseMapTool

class RectangleMapTool(BaseMapTool):
    def __init__(self, canvas, dlg):
        super().__init__(canvas, dlg)
        self.reset()
    
    def reset(self):
        super().reset()
        self.startPoint = self.endPoint = None
    
    def canvasPressEvent(self, e):
        self.startPoint = self.toMapCoordinates(e.pos())
        self.endPoint = self.startPoint
        self.isEmittingPoint = True
        self.showRect(self.startPoint, self.endPoint)
    
    def canvasReleaseEvent(self, e):
        self.isEmittingPoint = False
        r = self.rectangle()
        if r is not None:
            self.xMin = r.xMinimum()
            self.xMax = r.xMaximum()
            self.yMin = r.yMinimum()
            self.yMax = r.yMaximum()
            
            coord_text = self.dlg.lm.get_string("DRAW", "square_coordinates",
                            f"{self.xMin:.2f}", f"{self.yMin:.2f}", 
                            f"{self.xMax:.2f}", f"{self.yMax:.2f}")
            self.dlg.start_long_task("select_entities_in_area", self.dlg.dxf_handler.select_entities_in_area,
                                   self.xMin, self.xMax, self.yMin, self.yMax)
            self.update_dialog_coordinates(coord_text)
            self.finish_drawing()
    
    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return
        self.endPoint = self.toMapCoordinates(e.pos())
        self.showRect(self.startPoint, self.endPoint)
    
    def showRect(self, startPoint, endPoint):
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
            return
      
        points = [
            QgsPointXY(startPoint.x(), startPoint.y()),
            QgsPointXY(startPoint.x(), endPoint.y()),
            QgsPointXY(endPoint.x(), endPoint.y()),
            QgsPointXY(endPoint.x(), startPoint.y()),
            QgsPointXY(startPoint.x(), startPoint.y())
        ]
        
        for i, point in enumerate(points):
            self.rubberBand.addPoint(point, i == len(points)-1)
        
        self.rubberBand.show()

    def rectangle(self):
        if self.startPoint is None or self.endPoint is None:
            return None
        elif (self.startPoint.x() == self.endPoint.x() or self.startPoint.y() == self.endPoint.y()):
            return None
        return QgsRectangle(self.startPoint, self.endPoint)
