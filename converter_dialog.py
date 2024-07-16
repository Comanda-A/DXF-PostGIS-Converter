import os
from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import QFileDialog, QTreeWidgetItem
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsMessageLog, Qgis
from .db_manager import DBManager
import ezdxf


# Load UI file for PyQt
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'dialog_base.ui'))


class ConverterDialog(QtWidgets.QDialog, FORM_CLASS):
    """
    Dialog class for the DXF to DB converter plugin.
    """

    def __init__(self, parent=None):
        """Constructor."""
        super(ConverterDialog, self).__init__(parent)
        self.setupUi(self)
        self.pushButton.clicked.connect(self.select_dxf_button)
        self.treeWidget.itemChanged.connect(self.handle_item_changed)
        self.connectButton.clicked.connect(self.connect_to_db)
        self.msp = None
        self.tree_items = {}  # Dictionary for quick access to QTreeWidgetItem elements
        self.selectable = False
        self.fileIsOpen = False


    def select_dxf_button(self):
        """
        Handle DXF file selection and populate tree widget with layers and entities.
        """
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        file_name, _ = QFileDialog.getOpenFileName(self, "Select DXF File", "", "DXF Files (*.dxf);;All Files (*)", options=options)
        log_message(str(file_name))
        if file_name:
            self.label.setText(os.path.basename(file_name))
            try:
                dxf = ezdxf.readfile(file_name)
                self.msp = dxf.modelspace()
                self.fileIsOpen = True
                layer_groups = self.msp.groupby(dxfattrib="layer")
                self.populate_tree_widget(layer_groups)
            except IOError:
                log_message(f"File {file_name} not found or could not be read.")
                self.fileIsOpen = False
            except ezdxf.DXFStructureError:
                log_message(f"Invalid DXF file format: {file_name}")
                self.fileIsOpen = False
            self.set_selection_button_status()


    def handle_item_changed(self, item, column):
        """
        Handle changes in item check state and propagate changes to child items.
        """
        if (item.checkState(column) == Qt.Checked or item.checkState(column) == Qt.Unchecked) and not self.selectable:
            self.update_child_check_states(item, item.checkState(column))


    def update_child_check_states(self, parent_item, check_state):
        """
        Update check state of child items recursively.
        """
        for i in range(parent_item.childCount()):
            child_item = parent_item.child(i)
            child_item.setCheckState(0, check_state)
            self.update_child_check_states(child_item, check_state)


    def populate_tree_widget(self, layers):
        """
        Populate the tree widget with layers and entities from the DXF file.
        """
        self.treeWidget.clear()
        self.tree_items.clear()

        for layer, entities in layers.items():
            layer_item = QTreeWidgetItem([f'Слой: {layer}'])
            layer_item.setCheckState(0, Qt.Unchecked)
            self.treeWidget.addTopLevelItem(layer_item)
            self.tree_items[layer] = {'item': layer_item, 'entities': {}}

            for entity in entities:
                entity_description = f"Объект: {entity}"
                entity_item = QTreeWidgetItem([entity_description])
                entity_item.setCheckState(0, Qt.Unchecked)
                layer_item.addChild(entity_item)
                self.tree_items[layer]['entities'][entity_description] = entity_item

                attributes = [
                    f"Color: {entity.dxf.color}",
                    f"Linetype: {entity.dxf.linetype}",
                    f"Lineweight: {entity.dxf.lineweight}",
                    f"Ltscale: {entity.dxf.ltscale}",
                    f"Invisible: {entity.dxf.invisible}",
                    f"True Color: {entity.dxf.true_color}",
                    f"Transparency: {entity.dxf.transparency}"
                ]

                geometry_properties = {
                    'LINE': ["start", "end"],
                    'POINT': ["location"],
                    'CIRCLE': ["center", "radius"],
                    'ARC': ["center", "radius", "start_angle", "end_angle"],
                    'ELLIPSE': ["center", "major_axis", "extrusion", "ratio", "start_param", "end_param", "start_point", "end_point", "minor_axis"],
                    'SPLINE': ["degree"],
                    'INSERT': ["name", "insert", "xscale", "yscale", "zscale", "rotation", "row_count", "row_spacing", "column_count", "column_spacing"],
                    '3DSOLID': ["history_handle"],
                    '3DFACE': ["vtx0", "vtx1", "vtx2", "vtx3", "invisible_edges"],
                    'LWPOLYLINE': ["elevation", "flags", "const_width", "count"],
                    'MULTILEADER': ["arrow_head_handle", "arrow_head_size", "block_color", "block_connection_type", "block_record_handle", "block_rotation", "block_scale_vector", "content_type", "dogleg_length", "has_dogleg", "has_landing", "has_text_frame", "is_annotative", "is_text_direction_negative", "leader_extend_to_text", "leader_line_color"],
                    'TEXT': ["text", "insert", "align_point", "height", "rotation", "oblique", "style", "width", "halign", "valign", "text_generation_flag"],
                    'ATTRIB': ["tag", "text", "is_invisible", "is_const", "is_verify", "is_preset", "has_embedded_mtext_entity"],
                    'BODY': ["version", "flags", "uid", "acis_data", "sat", "has_binary_data"],
                    'ARC_DIMENSION': ["defpoint2", "defpoint3", "defpoint4", "start_angle", "end_angle", "is_partial", "has_leader", "leader_point1", "leader_point2", "dimtype"],
                    'HATCH': ["pattern_name", "solid_fill", "associative", "hatch_style", "pattern_type", "pattern_angle", "pattern_scale", "pattern_double", "n_seed_points", "elevation"],
                    'HELIX': ["axis_base_point", "start_point", "axis_vector", "radius", "turn_height", "turns", "handedness", "constrain"],
                    'IMAGE': ["insert", "u_pixel", "v_pixel", "image_size", "image_def_handle", "flags", "clipping", "brightness", "contrast", "fade", "clipping_boundary_type", "count_boundary_points", "clip_mode", "boundary_path", "image_def"],
                    '': [],
                    '': [],
                }

                geometry = []
                entity_type = entity.dxftype()
                if entity_type in geometry_properties:
                    geometry = [f"{prop.capitalize()}: {getattr(entity.dxf, prop)}" for prop in geometry_properties[entity_type]]

                attr_header = QTreeWidgetItem(['Атрибуты'])
                attr_header.setCheckState(0, Qt.Unchecked)
                entity_item.addChild(attr_header)
                geometry_header = QTreeWidgetItem(['Геометрия'])
                geometry_header.setCheckState(0, Qt.Unchecked)
                entity_item.addChild(geometry_header)

                for attr in attributes:
                    attr_item = QTreeWidgetItem([attr])
                    attr_item.setCheckState(0, Qt.Unchecked)
                    attr_header.addChild(attr_item)

                for geom in geometry:
                    geom_item = QTreeWidgetItem([geom])
                    geom_item.setCheckState(0, Qt.Unchecked)
                    geometry_header.addChild(geom_item)


    def select_area(self, xMin, xMax, yMin, yMax):
        """
        Select entities within a specified area and update tree widget.
        """
        self.selectable = True
        self.print_tree_items()
        window = ezdxf.select.Window((xMin, yMin), (xMax, yMax))
        layers_to_check = set()
        for entity in ezdxf.select.bbox_inside(window, self.msp):
            self.check_entity_in_tree(entity, layers_to_check)

        for layer in layers_to_check:
            self.tree_items[layer]['item'].setCheckState(0, Qt.Checked)
        self.selectable = False


    def check_entity_in_tree(self, entity, layers_to_check):
        """
        Check the corresponding tree widget item for the given entity.
        """
        layer_name = entity.dxf.layer
        entity_description = f"Объект: {entity}"

        if layer_name in self.tree_items:
            layer_data = self.tree_items[layer_name]['entities']
            if entity_description in layer_data:
                entity_item = layer_data[entity_description]
                entity_item.setCheckState(0, Qt.Checked)
                self.update_child_check_states(entity_item, Qt.Checked)
                layers_to_check.add(layer_name)


    def print_tree_items(self):
        """
        Print the tree widget items and their check states to the QGIS log.
        """
        for layer, data in self.tree_items.items():
            log_message(f"Layer: {layer}")
            layer_item = data['item']
            layer_checked = layer_item.checkState(0) == Qt.Checked
            log_message(f"  Layer Checked: {layer_checked}")
            for entity_description, entity_item in data['entities'].items():
                entity_checked = entity_item.checkState(0) == Qt.Checked
                log_message(f"    Entity: {entity_description}, Checked: {entity_checked}")


    def set_selection_button_status(self):
        """
        Enable or disable the selection button based on whether a file is open.
        """
        self.selectionButton.setEnabled(self.fileIsOpen)


    def connect_to_db(self):
        """
        Connect to the database using provided credentials.
        """
        host = self.hostLineEdit.text()
        port = self.portLineEdit.text()
        database = self.databaseLineEdit.text()
        user = self.userLineEdit.text()
        password = self.passwordLineEdit.text()

        self.db_manager = DBManager(host, port, database, user, password)
        if self.db_manager.connect():
            self.statusLabel.setText("Connected to database")
            self.push()
        else:
            self.statusLabel.setText("Failed to connect to database")


    def push(self):
        """
        Push selected objects to the database.
        """
        selected_objects = []
        for layer, data in self.tree_items.items():
            if data['item'].checkState(0) == Qt.Checked:
                for entity_description, entity_item in data['entities'].items():
                    if entity_item.checkState(0) == Qt.Checked:
                        attributes = []
                        geometry = []
                        for i in range(entity_item.childCount()):
                            child = entity_item.child(i)
                            if child.text(0) == 'Атрибуты':
                                attributes = [attr.text(0) for attr in self.get_checked_children(child)]
                            elif child.text(0) == 'Геометрия':
                                geometry = [geom.text(0) for geom in self.get_checked_children(child)]
                        selected_objects.append({
                            'layer': layer,
                            'entities': entity_item.text(0),
                            'attributes': attributes,
                            'geometry': geometry
                        })
        if selected_objects:
            self.db_manager.save_selected_objects(selected_objects)
            log_message("Push")


    def get_checked_children(self, parent_item):
        """
        Get all checked child items of a given parent item.
        """
        checked_children = []
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child.checkState(0) == Qt.Checked:
                checked_children.append(child)
        return checked_children

def log_message(message, tag='QGIS'):
    QgsMessageLog.logMessage(message, tag, Qgis.Info)
