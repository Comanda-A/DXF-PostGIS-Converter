import ezdxf
from ezdxf import select
from .logger import Logger
from qgis.core import QgsApplication
from PyQt5.QtCore import QThread, pyqtSignal, QObject, QTimer


class DXFHandler(QObject):
    progressChanged = pyqtSignal(int)
    def __init__(self, type_shape, type_selection):
        super().__init__()
        self.msp = None
        self.file_is_open = False
        self.type_shape = type_shape
        self.type_selection = type_selection
    def read_dxf_file(self, file_name):
        """
        Reads a DXF file and returns a dictionary groupby layer.
        """
        try:
            dxf = ezdxf.readfile(file_name)
            self.msp = dxf.modelspace()
            self.file_is_open = True

            self.process_entities(self.msp)

            return self.msp.groupby(dxfattrib="layer")
        except IOError:
            Logger.log_message(f"File {file_name} not found or could not be read.")
            self.file_is_open = False
        except ezdxf.DXFStructureError:
            Logger.log_message(f"Invalid DXF file format: {file_name}")
            self.file_is_open = False
        return None
    def select_entities_in_area(self, *args):
        """
        Select entities within the specified area based on the selection type.
        
        :param shape: Type of shape used for selection ('rect', 'circle', 'polygon').
        :param selection_type: Type of selection ('inside', 'outside', 'overlap', 'chained').
        :param args: Parameters for the shape (coordinates, center point, radius, etc.).
        """
        # Map selection types to selection functions
        selection_functions = {
            'inside': select.bbox_inside,
            'outside': select.bbox_outside,
            'overlap': select.bbox_overlap
        }
        
        if self.type_selection.currentText() not in selection_functions:
            raise ValueError(f"Unsupported selection type: {self.type_selection.currentText()}")
        
        # Map shape types to shape creation functions
        shape_creators = {
            'rect': lambda x_min, x_max, y_min, y_max: select.Window((x_min, y_min), (x_max, y_max)),
            'circle': lambda centerPoint, radius: select.Circle(centerPoint, radius),
            'polygon': lambda points: select.Polygon(points)
        }
        
        if self.type_shape.currentText() not in shape_creators:
            raise ValueError(f"Unsupported shape type: {self.type_shape.currentText()}")
        
        # Create the shape object
        shape_obj = shape_creators[self.type_shape.currentText()](*args)
        
        # Get the appropriate selection function
        selection_func = selection_functions[self.type_selection.currentText()]
        
        # Select entities
        entities = list(selection_func(shape_obj, self.msp))
        
        # Process and return entities
        self.process_entities(entities)
        return entities
    #TODO: пустышка для видимости прогресса (возможно получится подвязать к реальному прогрессу)
    def process_entities(self, entities):
        total_entities = len(entities)
        for i, entity in enumerate(entities):
            # Simulate processing of each entity
            progress = int((i + 1) / total_entities * 100)
            self.progressChanged.emit(progress)
