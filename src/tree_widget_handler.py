from qgis.PyQt.QtWidgets import QTreeWidgetItem, QProgressDialog
from qgis.PyQt.QtCore import Qt
from PyQt5.QtWidgets import QTreeWidgetItem, QPushButton, QWidget, QHBoxLayout, QHeaderView

from qgis.core import QgsApplication
from shapely.geometry import Point
from .logger.logger import Logger


class TreeWidgetHandler:

    def __init__(self, tree_widget, selectable: bool = True):
        self.tree_widget = tree_widget
        self.tree_items = {}  # Dictionary for quick access to QTreeWidgetItem elements
        self.selectable = False
        self.tree_widget.itemChanged.connect(self.handle_item_changed)

        # Set the stretch factors for the columns
        self.tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree_widget.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)

    def handle_item_changed(self, item, column):
        if (item.checkState(column) == Qt.Checked or item.checkState(column) == Qt.Unchecked) and not self.selectable:
            self.update_child_check_states(item, item.checkState(column))

    def update_child_check_states(self, parent_item, check_state):
        for i in range(parent_item.childCount()):
            child_item = parent_item.child(i)
            child_item.setCheckState(0, check_state)
            self.update_child_check_states(child_item, check_state)

    def add_remove_button_to_item(self, item, tree_widget):
        # Создаем кнопку
        remove_button = QPushButton('Удалить')

        # Устанавливаем размер кнопки
        remove_button.setFixedSize(80, 20)

        # Привязываем кнопку к обработчику нажатия
        remove_button.clicked.connect(lambda: self.remove_item(item, tree_widget))

        # Создаем контейнер для кнопки
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.addWidget(remove_button)
        layout.setAlignment(Qt.AlignRight)
        layout.setContentsMargins(0, 0, 0, 0)
        widget.setLayout(layout)

        # Добавляем кнопку в соответствующую колонку узла дерева
        tree_widget.setItemWidget(item, 1, widget)

    def remove_item(self, item, tree_widget):
        # Удаляем элемент
        index = tree_widget.indexOfTopLevelItem(item)
        if index != -1:
            tree_widget.takeTopLevelItem(index)
        else:
            parent = item.parent()
            parent.removeChild(item)

    def populate_tree_widget(self, layers):

        layers, full_path = layers[0], layers[1]

        file_name = os.path.basename(full_path)

        # Создаем элемент для file_name на вершине дерева
        file_item = QTreeWidgetItem([f'Файл: {file_name}'])
        file_item.setCheckState(0, Qt.Unchecked)
        self.tree_widget.addTopLevelItem(file_item)

        self.add_remove_button_to_item(file_item, self.tree_widget)

        for layer, entities in layers.items():
            layer_item = QTreeWidgetItem([f'Layer: {layer}'])
            layer_item.setCheckState(0, Qt.Unchecked)
            file_item.addChild(layer_item)
            self.tree_items[layer] = {'item': layer_item, 'entities': {}}

            for entity in entities:
                entity_description = f"{entity}"
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

        attr_header = QTreeWidgetItem(['Attributes'])
        attr_header.setCheckState(0, Qt.Unchecked)
        entity_item.addChild(attr_header)
        geometry_header = QTreeWidgetItem(['Geometry'])
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
        self.clear_all_checks()
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
            parent = self.tree_items[layer]['item'].parent()
            parent.setCheckState(0, Qt.Checked)

        self.selectable = False

    def check_entity_in_tree(self, entity, layers_to_check):
        layer_name = entity.dxf.layer
        entity_description = f"{entity}"

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

    def get_all_checked_entities(self):
        checked_entities = {}

        for layer, data in self.tree_items.items():
            if data['item'].checkState(0) == Qt.Checked:
                for entity_description, entity_item in data['entities'].items():
                    if entity_item.checkState(0) == Qt.Checked:
                        attributes = []
                        geometry = []
                        for i in range(entity_item.childCount()):
                            child = entity_item.child(i)
                            if child.text(0) == 'Attributes':
                                attributes = [attr.text(0) for attr in self.get_checked_children(child)]
                            elif child.text(0) == 'Geometry':
                                geometry = [geom.text(0) for geom in self.get_checked_children(child)]

                        if layer not in checked_entities:
                            checked_entities[layer] = []

                        checked_entities[layer].append({
                            'entity_description': entity_item.text(0),
                            'attributes': attributes,
                            'geometry': geometry
                        })

        return checked_entities

    def clear_all_checks(self):
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            item.setCheckState(0, Qt.Unchecked)
            self.update_child_check_states(item, Qt.Unchecked)

