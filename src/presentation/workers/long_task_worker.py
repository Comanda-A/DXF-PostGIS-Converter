from qgis.PyQt.QtCore import QThread, pyqtSignal

class LongTaskWorker(QThread):
    finished = pyqtSignal(int, object)  # task_id, result
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # current, total
    
    # Статический счетчик task_id
    _task_counter = 0

    def __init__(self, func, *args):
        super().__init__()
        self.task_id = LongTaskWorker._next_task_id()
        self.func = func
        self.args = args
        self.is_cancelled = False
        self.is_finished = False

    def run(self):
        try:
            # Если функция имеет атрибут progress, связываем его с сигналом progress
            if hasattr(self.func, 'progress'):
                self.func.progress = self.progress.emit
                
            result = self.func(*self.args)
            
            if not self.is_cancelled:
                self.finished.emit(self.task_id, result)
        except Exception as e:
            self.error.emit(str(e))
        
        self.is_finished = True

    def cancel(self):
        self.is_cancelled = True
        
    @classmethod
    def _next_task_id(cls):
        cls._task_counter += 1
        return cls._task_counter