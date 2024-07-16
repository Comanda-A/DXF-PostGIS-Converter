
import ezdxf
from collections import defaultdict


class DxfHandler:
    """Class for handling and processing DXF files."""

    def __init__(self, filepath):
        """
        Initialize the handler with the path to a DXF file.

        :param filepath: Path to the DXF file.
        """
        self.filepath = filepath
        self.doc = None
        self.layers = defaultdict(list)
        self._read_dxf()

    def _read_dxf(self):
        """
        Read the DXF file and process its layers.
        """
        try:
            self.doc = ezdxf.readfile(self.filepath)
        except IOError:
            print(f"File {self.filepath} not found or could not be read.")
        except ezdxf.DXFStructureError:
            print(f"Invalid DXF file format: {self.filepath}")
        else:
            self._process_layers()

    def _process_layers(self):
        """
        Process the layers of the DXF file and store entities in the layers dictionary.
        """
        if self.doc:
            for entity in self.doc.modelspace():
                layer_name = entity.dxf.layer
                self.layers[layer_name].append(entity)

    def get_entities_by_layer(self, layer_name):
        """
        Get all entities from a specified layer.

        :param layer_name: Name of the layer.
        :return: List of entities in the specified layer.
        """
        return self.layers.get(layer_name, [])

    def get_all_layers(self):
        """
        Get a list of all layer names.

        :return: List of all layer names.
        """
        return list(self.layers.keys())

    def get_all_entities(self):
        """
        Get all entities from all layers.

        :return: List of all entities.
        """
        all_entities = []
        for entities in self.layers.values():
            all_entities.extend(entities)
        return all_entities