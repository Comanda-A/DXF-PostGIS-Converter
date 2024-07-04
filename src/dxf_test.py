from dxf.dxf import DXF


if __name__ == "__main__":

    dxf_data = DXF('G:\Python projects\DXF-PostGIS-Converter\dxf_examples\ex1.dxf')

    print("All layers:", dxf_data.get_all_layers())

    for layer in dxf_data.get_all_layers():
        print(f"Entities in layer {layer}:", dxf_data.get_entities_by_layer(layer))
    