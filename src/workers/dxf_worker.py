from qgis.PyQt.QtCore import QThread, pyqtSignal

class DXFWorker(QThread):
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, dxf_handler, files):
        super().__init__()
        self.dxf_handler = dxf_handler
        self.files = files
        self.is_cancelled = False

    def run(self):
        try:
            results = []
            total_files = len(self.files)
            
            for i, file_name in enumerate(self.files):
                if self.is_cancelled:
                    break
                    
                self.progress.emit(i + 1, total_files)
                result = self.dxf_handler.read_dxf_file(file_name)
                results.append(result)
                
            self.finished.emit(results)
            
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self.is_cancelled = True
