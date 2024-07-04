import ezdxf
from collections import defaultdict

class DXF:
    def __init__(self, filepath):
        self.filepath = filepath
        self.doc = None
        self.layers = defaultdict(list)

        self._read_dxf()

    def _read_dxf(self):
        try:
            self.doc = ezdxf.readfile(self.filepath)
        except IOError:
            print(f"File {self.filepath} not found or could not be read.")
        except ezdxf.DXFStructureError:
            print(f"Invalid DXF file format: {self.filepath}")
        else:
            self._process_layers()

    def _process_layers(self):
        if self.doc:
            for entity in self.doc.modelspace():
                layer_name = entity.dxf.layer
                self.layers[layer_name].append(entity)

    def get_entities_by_layer(self, layer_name):
        return self.layers.get(layer_name, [])

    def get_all_layers(self):
        return list(self.layers.keys())

    def get_all_entities(self):
        all_entities = []
        for entities in self.layers.values():
            all_entities.extend(entities)
        return all_entities
    

