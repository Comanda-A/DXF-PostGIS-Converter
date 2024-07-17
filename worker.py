from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from .logger import Logger

class Worker(QObject):
    progressChanged = pyqtSignal(int)
    finished = pyqtSignal(str, object)  # Signal to emit the task identifier and result
    
    def __init__(self, task_id, func, *args):
        super().__init__()
        self.func = func
        self.task_id = task_id
        self.args = args
    
    @pyqtSlot()
    def process(self):
        """
        Executes the function specified in the `func` attribute with the arguments specified in the `args` attribute.
        If the function execution is successful, emits the `finished` signal with the `task_id` and the result of the function.
        If an exception occurs during the function execution, logs the exception message using the `Logger.log_message` method and emits the `finished` signal with the `task_id` and `None` as the result.
        """
        try:
            result = self.func(*self.args)
            self.finished.emit(self.task_id, result)
        except Exception as e:
            Logger.log_message(str(e))
            self.finished.emit(self.task_id, None)
