from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QFormLayout

class FieldMappingDialog(QDialog):
    def __init__(self, layer_fields, table_columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Field Mapping")
        self.layer_fields = layer_fields
        self.table_columns = table_columns
        self.mapping = {}

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        form_layout = QFormLayout()

        # For each field in the layer, create a combo box to map it to a table column
        self.comboboxes = {}
        for field in self.layer_fields:
            label = QLabel(field)
            combobox = QComboBox()
            combobox.addItems(self.table_columns)
            form_layout.addRow(label, combobox)
            self.comboboxes[field] = combobox

        layout.addLayout(form_layout)

        # OK and Cancel buttons
        btn_layout = QVBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")

        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        layout.addWidget(ok_btn)
        layout.addWidget(cancel_btn)

        self.setLayout(layout)

    def get_mapping(self):
        # Create mapping from the UI selections
        for field, combobox in self.comboboxes.items():
            self.mapping[field] = combobox.currentText()
        return self.mapping

