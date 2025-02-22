from qgis.PyQt.QtCore import QThread, pyqtSignal

class LongTaskWorker(QThread):
    finished = pyqtSignal(str, object)  # task_id, result
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # current, total

    def __init__(self, task_id, func, *args):
        super().__init__()
        self.task_id = task_id
        self.func = func
        self.args = args
        self.is_cancelled = False

    def run(self):
        try:
            # If function has progress attribute, connect it to progress signal
            if hasattr(self.func, 'progress'):
                self.func.progress = self.progress.emit
                
            result = self.func(*self.args)
            if not self.is_cancelled:
                self.finished.emit(self.task_id, result)
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self.is_cancelled = True
