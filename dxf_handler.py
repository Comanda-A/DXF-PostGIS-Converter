import ezdxf
from ezdxf import select
from .logger import Logger
from qgis.core import QgsApplication
from PyQt5.QtCore import QThread, pyqtSignal, QObject, QTimer


class DXFHandler(QObject):
    progressChanged = pyqtSignal(int)
    def __init__(self):
        super().__init__()
        self.msp = None
        self.file_is_open = False
       
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
    def select_entities_in_area(self, x_min, x_max, y_min, y_max):
        """
        Select entities within the specified area.
        """
        window = select.Window((x_min, y_min), (x_max, y_max))
        entities = list(ezdxf.select.bbox_inside(window, self.msp))
        self.process_entities(entities)

        return entities
    #TODO: пустышка для видимости прогресса (возможно получится подвязать к реальному прогрессу)
    def process_entities(self, entities):
        total_entities = len(entities)
        for i, entity in enumerate(entities):
            # Simulate processing of each entity
            progress = int((i + 1) / total_entities * 100)
            self.progressChanged.emit(progress)
