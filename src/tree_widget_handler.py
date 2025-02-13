from qgis.PyQt.QtWidgets import QTreeWidgetItem, QProgressDialog, QTreeWidgetItem, QPushButton, QWidget, QHBoxLayout, QHeaderView
from qgis.PyQt.QtCore import Qt

from qgis.core import QgsApplication
from shapely.geometry import Point
from .logger.logger import Logger


def remove_item(item, tree_widget):
    # Удаляем элемент
    index = tree_widget.indexOfTopLevelItem(item)
    if index != -1:
        tree_widget.takeTopLevelItem(index)
    else:
        parent = item.parent()
        parent.removeChild(item)


def add_remove_button_to_item(item, tree_widget):
    # Создаем кнопку
    remove_button = QPushButton('Удалить')

    # Устанавливаем размер кнопки
    remove_button.setFixedSize(80, 20)

    # Привязываем кнопку к обработчику нажатия
    remove_button.clicked.connect(lambda: remove_item(item, tree_widget))

    # Создаем контейнер для кнопки
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.addWidget(remove_button)
    layout.setAlignment(Qt.AlignRight)
    layout.setContentsMargins(0, 0, 0, 0)
    widget.setLayout(layout)

    # Добавляем кнопку в соответствующую колонку узла дерева
    tree_widget.setItemWidget(item, 1, widget)


class TreeWidgetHandler:

    def __init__(self, tree_widget, selectable: bool = True):
        self.tree_widget = tree_widget
        self.tree_items = {}  # Dictionary for quick access to QTreeWidgetItem elements
        self.selectable = False
        self.tree_widget.itemChanged.connect(self.handle_item_changed)
        self.layer_count = 0
        self.selected_layers_count = 0
        self.layer_stats = {}  # Cache for layer statistics
        self.update_timer = None
        self.batch_update = False
        self.total_entities = 0  # Общее количество объектов во всех слоях
        self.selected_total_entities = 0  # Общее количество выбранных объектов

        # Set the stretch factors for the columns
        self.tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree_widget.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)

    def handle_item_changed(self, item, column):
        if self.batch_update or self.selectable:
            return

        if item.checkState(column) in [Qt.Checked, Qt.Unchecked]:
            self.batch_update = True
            
            # Если это корневой элемент файла
            if not item.parent():
                self.update_child_check_states(item, item.checkState(column))
                # Обновляем статистику для всех слоев
                for layer_name in self.tree_items.keys():
                    self.update_layer_statistics(layer_name)
            else:
                # Находим корневой элемент слоя
                layer_item = item
                while layer_item.parent() and layer_item.parent().parent():
                    layer_item = layer_item.parent()

                # Получаем имя слоя
                layer_name = layer_item.text(0).split('|')[0].replace('Layer:', '').strip()
                
                self.update_child_check_states(item, item.checkState(column))
                self.update_parent_check_states(item)
                self.update_layer_statistics(layer_name)
            
            self.batch_update = False
            self.update_selection_count()

    def update_child_check_states(self, parent_item, check_state):
        for i in range(parent_item.childCount()):
            child_item = parent_item.child(i)
            child_item.setCheckState(0, check_state)
            self.update_child_check_states(child_item, check_state)

    def update_parent_check_states(self, item):
        parent = item.parent()
        if not parent:
            return

        child_count = parent.childCount()
        checked_count = 0
        partial_count = 0

        for i in range(child_count):
            child = parent.child(i)
            if child.checkState(0) == Qt.Checked:
                checked_count += 1
            elif child.checkState(0) == Qt.PartiallyChecked:
                partial_count += 1

        if checked_count == child_count:
            parent.setCheckState(0, Qt.Checked)
        elif checked_count > 0 or partial_count > 0:
            parent.setCheckState(0, Qt.PartiallyChecked)
        else:
            parent.setCheckState(0, Qt.Unchecked)

        self.update_parent_check_states(parent)

    def populate_tree_widget(self, layers):

        layers, file_name = layers[0], layers[1]
        self.layer_count = len(layers)
        
        # Подсчет общего количества объектов
        self.total_entities = sum(len(entities) for entities in layers.values())
        self.selected_total_entities = 0

        # Initialize statistics
        for layer, entities in layers.items():
            self.layer_stats[layer] = {
                'total': len(entities),
                'selected': 0
            }

        # Создаем элемент для file_name на вершине дерева
        file_item = QTreeWidgetItem([f'Файл: {file_name} | ({self.layer_count} слоев, {self.total_entities} объектов)'])
        file_item.setCheckState(0, Qt.Unchecked)
        self.tree_widget.addTopLevelItem(file_item)

        add_remove_button_to_item(file_item, self.tree_widget)

        # Отключаем обновления UI во время заполнения
        self.tree_widget.setUpdatesEnabled(False)

        for layer, entities in layers.items():
            entity_count = len(entities)
            layer_item = QTreeWidgetItem([f'Layer: {layer} | ({entity_count} объектов | выбрано: 0)'])
            layer_item.setCheckState(0, Qt.Unchecked)
            file_item.addChild(layer_item)
            self.tree_items[layer] = {'item': layer_item, 'entities': {}}

            # Batch add entities
            entity_items = []
            for entity in entities:
                entity_description = f"{entity}"
                entity_item = QTreeWidgetItem([entity_description])
                entity_item.setCheckState(0, Qt.Unchecked)
                entity_items.append(entity_item)
                self.tree_items[layer]['entities'][entity_description] = entity_item

            layer_item.addChildren(entity_items)

            # Отложенное добавление атрибутов
            for entity, entity_item in zip(entities, entity_items):
                self.add_entity_attributes_and_geometry(entity_item, entity)

        self.tree_widget.setUpdatesEnabled(True)

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
        self.batch_update = True
        self.tree_widget.setUpdatesEnabled(False)
        
        self.clear_all_checks()
        self.selectable = True
        layers_to_check = {}
        
        # Группируем entities по слоям для оптимизации
        for entity in entities:
            layer_name = entity.dxf.layer
            if layer_name not in layers_to_check:
                layers_to_check[layer_name] = []
            layers_to_check[layer_name].append(entity)

        # Обрабатываем каждый слой
        total_steps = len(entities)
        progress_dialog = QProgressDialog("Проверка объектов...", "Отмена", 0, total_steps)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.show()

        processed = 0
        for layer_name, layer_entities in layers_to_check.items():
            if layer_name in self.tree_items:
                layer_data = self.tree_items[layer_name]
                
                # Массовое обновление элементов слоя
                for entity in layer_entities:
                    entity_description = f"{entity}"
                    if entity_description in layer_data['entities']:
                        entity_item = layer_data['entities'][entity_description]
                        entity_item.setCheckState(0, Qt.Checked)
                        self.update_parent_check_states(entity_item)
                
                # Обновляем статистику слоя
                self.update_layer_statistics(layer_name)
                
                processed += len(layer_entities)
                progress_dialog.setValue(processed)
                QgsApplication.processEvents()

                if progress_dialog.wasCanceled():
                    break

        progress_dialog.close()
        
        self.selectable = False
        self.batch_update = False
        self.tree_widget.setUpdatesEnabled(True)
        self.update_selection_count()

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

    #TODO: модернизируй согласно новой структуре (если это необходимо)
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
        self.batch_update = True
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            item.setCheckState(0, Qt.Unchecked)
            self.update_child_check_states(item, Qt.Unchecked)
        self.batch_update = False
        self.update_selection_count()

    def update_selection_count(self):
        """Обновляет информацию о выбранных слоях и объектах"""
        self.selected_layers_count = 0
        self.selected_total_entities = 0

        # Подсчитываем выбранные слои и объекты
        for layer_name, layer_data in self.tree_items.items():
            if layer_data['item'].checkState(0) in [Qt.Checked, Qt.PartiallyChecked]:
                self.selected_layers_count += 1
            self.selected_total_entities += self.layer_stats[layer_name]['selected']
        
        # Обновляем текст корневого элемента
        root_item = self.tree_widget.topLevelItem(0)
        if root_item:
            file_name = root_item.text(0).split('(')[0].strip()
            if self.selected_layers_count > 0:
                root_item.setText(0, (
                    f'{file_name} ({self.layer_count} слоев | '
                    f'выбрано {self.selected_layers_count}/{self.layer_count} | '
                    f'объектов {self.selected_total_entities}/{self.total_entities})'
                ))
            else:
                root_item.setText(0, f'{file_name} ({self.layer_count} слоев, {self.total_entities} объектов)')

    def update_layer_statistics(self, layer_name):
        """Обновляет статистику выбранных объектов для слоя"""
        if layer_name in self.tree_items:
            layer_data = self.tree_items[layer_name]
            layer_item = layer_data['item']
            
            # Подсчет только прямых дочерних элементов (объектов) слоя
            total_entities = 0
            selected_entities = 0
            
            for i in range(layer_item.childCount()):
                entity_item = layer_item.child(i)
                if not entity_item.text(0) in ['Attributes', 'Geometry']:
                    total_entities += 1
                    if entity_item.checkState(0) == Qt.Checked:
                        selected_entities += 1
            
            self.layer_stats[layer_name]['total'] = total_entities
            self.layer_stats[layer_name]['selected'] = selected_entities
            
            # Обновляем текст элемента слоя
            layer_item.setText(0, f'Layer: {layer_name} | ({total_entities} объектов | выбрано: {selected_entities}/{total_entities})')
