
from abc import ABC, abstractmethod

class ILogger(ABC):
    
    @abstractmethod
    def is_enabled(self) -> bool:
        pass
    
    @abstractmethod
    def set_enabled(self, enabled: bool):
        pass
    
    @abstractmethod
    def message(self, message, tag='DXF-PostGIS-Converter'):
        pass
    
    @abstractmethod
    def warning(self, message, tag='DXF-PostGIS-Converter'):
        pass
    
    @abstractmethod
    def error(self, message, tag='DXF-PostGIS-Converter'):
        pass
