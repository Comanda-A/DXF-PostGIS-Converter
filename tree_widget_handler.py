from qgis.PyQt.QtWidgets import QTreeWidgetItem, QProgressDialog
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsApplication

from .logger import Logger

class TreeWidgetHandler:
    def __init__(self, tree_widget):
        self.tree_widget = tree_widget
        self.tree_items = {}  # Dictionary for quick access to QTreeWidgetItem elements
        self.selectable = False

    def handle_item_changed(self, item, column):
        if (item.checkState(column) == Qt.Checked or item.checkState(column) == Qt.Unchecked) and not self.selectable:
            self.update_child_check_states(item, item.checkState(column))

    def update_child_check_states(self, parent_item, check_state):
        for i in range(parent_item.childCount()):
            child_item = parent_item.child(i)
            child_item.setCheckState(0, check_state)
            self.update_child_check_states(child_item, check_state)

    def populate_tree_widget(self, layers):
        self.tree_widget.clear()
        self.tree_items.clear()

        for layer, entities in layers.items():
            layer_item = QTreeWidgetItem([f'Слой: {layer}'])
            layer_item.setCheckState(0, Qt.Unchecked)
            self.tree_widget.addTopLevelItem(layer_item)
            self.tree_items[layer] = {'item': layer_item, 'entities': {}}

            for entity in entities:
                entity_description = f"Объект: {entity}"
                entity_item = QTreeWidgetItem([entity_description])
                entity_item.setCheckState(0, Qt.Unchecked)
                layer_item.addChild(entity_item)
                self.tree_items[layer]['entities'][entity_description] = entity_item

                self.add_entity_attributes_and_geometry(entity_item, entity)

    def add_entity_attributes_and_geometry(self, entity_item, entity):
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
            'IMAGE': ["insert", "u_pixel", "v_pixel", "image_size", "image_def_handle", "flags", "clipping", "brightness", "contrast", "fade", "clipping_boundary_type", "count_boundary_points", "clip_mode", "boundary_path", "image_def"]
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

    def select_area(self, entities):
        self.selectable = True
        #self.print_tree_items()        
        layers_to_check = set()
        
        # Создаем диалог прогресса
        progress_dialog = QProgressDialog("Проверка объектов...", "Отмена", 0, len(entities))
        progress_dialog.setWindowTitle("Прогресс")
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.show()

        for i, entity in enumerate(entities):
            # Проверка, была ли нажата кнопка отмены
            if progress_dialog.wasCanceled():
                break
            
            self.check_entity_in_tree(entity, layers_to_check)
            
            # Обновление прогресса
            progress_dialog.setValue(i)
            
            # Обновление интерфейса
            QgsApplication.processEvents()

        progress_dialog.close()

        for layer in layers_to_check:
            self.tree_items[layer]['item'].setCheckState(0, Qt.Checked)
        self.selectable = False

    def check_entity_in_tree(self, entity, layers_to_check):
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
        for layer, data in self.tree_items.items():
            Logger.log_message(f"Layer: {layer}")
            layer_item = data['item']
            layer_checked = layer_item.checkState(0) == Qt.Checked
            Logger.log_message(f"  Layer Checked: {layer_checked}")
            for entity_description, entity_item in data['entities'].items():
                entity_checked = entity_item.checkState(0) == Qt.Checked
                Logger.log_message(f"    Entity: {entity_description}, Checked: {entity_checked}")

    def get_checked_children(self, parent_item):
        checked_children = []
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child.checkState(0) == Qt.Checked:
                checked_children.append(child)
        return checked_children
