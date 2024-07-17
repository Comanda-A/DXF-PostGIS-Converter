from PyQt5.QtCore import QThread
from .worker import Worker
from .logger import Logger
class WorkerHandler:
    def __init__(self):
        self.worker_thread = None
        self.worker = None
    def start_worker(self, func, finished_callback, progress_callback=None, real_func=None, task_id=None, *args):
        """
        Starts a worker by creating a new Worker object, setting up a QThread, moving the Worker object to the thread,
        connecting progress signals if available, and starting the worker thread.
        
        Args:
            self: WorkerHandler object.
            func: The function to be executed.
            finished_callback: The callback function to be called once the worker finishes.
            progress_callback: The callback function to update progress during the worker execution.
            real_func: The real function to be executed in the worker.
            task_id: The identifier of the task.
            *args: Variable length argument list.
        """
        self.worker = Worker(task_id, func, *args)
        self.worker_thread = QThread()

        self.worker.moveToThread(self.worker_thread)
        if progress_callback:
            if hasattr(real_func, 'progressChanged'):
                real_func.progressChanged.connect(progress_callback)
                Logger.log_message("Connected handler progressChanged signal to progress_callback")
            else:
                self.worker.progressChanged.connect(progress_callback)
        self.worker.finished.connect(finished_callback)
        self.worker_thread.started.connect(self.worker.process)

        self.worker_thread.start()

    def stop_worker(self):
        """
        Stops the worker thread and cleans up the worker and thread objects.
        """
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker.deleteLater()
            self.worker_thread.deleteLater()
