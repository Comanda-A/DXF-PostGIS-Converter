from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton

class FieldMappingDialog(QDialog):
    def __init__(self, layer_fields, table_fields, parent=None):
        super(FieldMappingDialog, self).__init__(parent)
        self.setWindowTitle("Field Mapping")
        self.layer_fields = layer_fields
        self.table_fields = table_fields
        self.mapping = {}

        layout = QVBoxLayout(self)

        # Create dropdowns for each field in the layer
        for layer_field in self.layer_fields:
            h_layout = QHBoxLayout()
            label = QLabel(layer_field)
            combo = QComboBox()
            combo.addItems([''] + self.table_fields)
            h_layout.addWidget(label)
            h_layout.addWidget(combo)
            layout.addLayout(h_layout)

            # Store mapping in the form of {layer_field: table_field}
            combo.currentIndexChanged.connect(lambda index, lf=layer_field, c=combo: self.update_mapping(lf, c))

        # Add Ok and Cancel buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

    def update_mapping(self, layer_field, combo_box):
        selected_table_field = combo_box.currentText()
        if selected_table_field:
            self.mapping[layer_field] = selected_table_field
        else:
            self.mapping.pop(layer_field, None)

    def get_mapping(self):
        return self.mapping