
from typing import TypeVar, Callable
from qgis.PyQt.QtCore import QObject, pyqtSignal
from ...application.events import IEvent

T = TypeVar('T', covariant=True)

class QtEvent(IEvent[T]):
    
    class _SignalHolder(QObject):
        """Внутренний класс для хранения сигнала"""
        event = pyqtSignal(object)
    
    def __init__(self):
        self._signal_holder = self._SignalHolder()

    def connect(self, receiver: Callable[[T], None]) -> None:
        """Подключить слот к сигналу"""
        self._signal_holder.event.connect(receiver)

    def disconnect(self, receiver: Callable[[T], None]) -> None:
        """Отключить слот от сигнала"""
        if receiver:
            self._signal_holder.event.disconnect(receiver)

    def emit(self, data: T) -> None:
        """Испустить сигнал с данными"""
        self._signal_holder.event.emit(data)

    def clear(self) -> None:
        """Отключить все слоты"""
        self._signal_holder.event.disconnect()
