from qgis.PyQt.QtWidgets import QProgressDialog, QTreeWidgetItem, QPushButton, QWidget, QHBoxLayout, QHeaderView, QMessageBox
from qgis.PyQt.QtCore import Qt, pyqtSignal, QObject

from qgis.core import QgsApplication
from .logger.logger import Logger
from .localization.localization_manager import LocalizationManager


def remove_item(item, tree_widget):
    # Удаляем элемент
    index = tree_widget.indexOfTopLevelItem(item)
    if index != -1:
        tree_widget.takeTopLevelItem(index)
    else:
        parent = item.parent()
        parent.removeChild(item)


def add_remove_button_to_item(item, tree_widget):
    # Получаем менеджер локализации
    lm = LocalizationManager.instance()
    
    # Создаем кнопку
    remove_button = QPushButton(lm.get_string("TREE_WIDGET_HANDLER", "remove_button"))

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


def get_word_form(number: int, forms: list) -> str:
    """
    Возвращает правильную форму слова в зависимости от числа
    forms - список из трех форм слова, например: ['слой', 'слоя', 'слоев']
    """
    if number % 100 in [11, 12, 13, 14]:
        return forms[2]
    
    remainder = number % 10
    if remainder == 1:
        return forms[0]
    if remainder in [2, 3, 4]:
        return forms[1]
    return forms[2]


class TreeWidgetHandler(QObject):
    # Добавляем сигнал для оповещения об изменении выбора
    selection_changed = pyqtSignal(str)
    # Сигнал для оповещения о создании новой структуры дерева
    tree_structure_created = pyqtSignal(str, dict)  # file_name, layers_dict
    # Сигнал для оповещения об изменении конкретного слоя
    layer_check_changed = pyqtSignal(str, str, bool)  # file_name, layer_name, checked

    def __init__(self, tree_widget, selectable: bool = True):
        super().__init__()  # Initialize QObject
        if tree_widget is None: return
        self.tree_widget = tree_widget
        self.tree_items = {}  # Structure: {file_name: {layer_name: {'item': item, 'entities': {}}}}
        self.selectable = False
        self.tree_widget.itemChanged.connect(self.handle_item_changed)
        self.layer_count = 0
        self.selected_layers_count = 0
        self.layer_stats = {}  # Cache for layer statistics
        self.update_timer = None
        self.batch_update = False
        self.total_entities = 0  # Общее количество объектов во всех слоях
        self.selected_total_entities = 0  # Общее количество выбранных объектов
        self.selected_file = None
        self.files_data = {}  # Tracking statistics per file
        self.current_file_name = None  # Добавляем отслеживание текущего файла
        self.updating_selection = False  # Флаг для отслеживания программного обновления выбора
        # Set the stretch factors for the columns
        self.tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree_widget.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        
        # Инициализация менеджера локализации
        self.lm = LocalizationManager.instance()

        # Добавляем формы слов для склонения из локализации
        self.word_forms = {
            'layer': self.lm.get_string("TREE_WIDGET_HANDLER", "word_forms")["layer"],
            'entity': self.lm.get_string("TREE_WIDGET_HANDLER", "word_forms")["entity"],
        }

    def _reset_file_text(self, file_item, file_name):
        """Сбрасывает текст файла к начальному виду"""
        if file_name in self.files_data:
            file_data = self.files_data[file_name]
            layers_word = get_word_form(file_data['layer_count'], self.word_forms['layer'])
            entities_word = get_word_form(file_data['total_entities'], self.word_forms['entity'])
            file_item.setText(0, 
                self.lm.get_string("TREE_WIDGET_HANDLER", "file_text",
                                  file_name, file_data["layer_count"], layers_word,
                                  file_data["total_entities"], entities_word)            )

    def handle_item_changed(self, item, column):
        if self.batch_update or self.selectable or self.updating_selection:
            return

        root_item = item
        while root_item.parent():
            root_item = root_item.parent()

        try:
            current_file_name = self._get_file_name_from_item(root_item)
            
            if current_file_name and current_file_name != "":
                # Если файл еще не выбран, и мы выбираем слой или его элементы
                if not self.selected_file and item.parent():
                    self.selected_file = root_item
                    self.current_file_name = current_file_name
                    root_item.setCheckState(0, Qt.PartiallyChecked)
                    
                # Проверяем выбор в другом файле
                elif self.selected_file and root_item != self.selected_file and item.checkState(column) in [Qt.Checked, Qt.PartiallyChecked]:
                    reply = QMessageBox.question(
                        None,
                        self.lm.get_string("TREE_WIDGET_HANDLER", "selection_confirm_title"),
                        self.lm.get_string("TREE_WIDGET_HANDLER", "selection_confirm_message"),
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )

                    if reply == QMessageBox.Yes:
                        self.batch_update = True
                        # Очищаем статистику предыдущего файла
                        prev_file_name = self._get_file_name_from_item(self.selected_file)
                        if prev_file_name in self.files_data:
                            self._clear_file_statistics(prev_file_name)
                            # Сбрасываем текст предыдущего файла
                            self._reset_file_text(self.selected_file, prev_file_name)
                        
                        self.selected_file.setCheckState(0, Qt.Unchecked)
                        self.update_child_check_states(self.selected_file, Qt.Unchecked)
                        self.selected_file = root_item
                        self.current_file_name = current_file_name
                        self.batch_update = False
                    else:
                        self.batch_update = True
                        item.setCheckState(0, Qt.Unchecked)
                        self.batch_update = False
                        return

                # Обновляем текущий файл
                if not item.parent():
                    if item.checkState(column) in [Qt.Checked, Qt.PartiallyChecked]:
                        # Если был выбран другой файл, сбрасываем его текст
                        if self.selected_file and self.selected_file != root_item:
                            prev_file_name = self._get_file_name_from_item(self.selected_file)
                            self._reset_file_text(self.selected_file, prev_file_name)
                        
                        self.selected_file = item
                        self.current_file_name = current_file_name
                    else:                        
                        # При снятии выбора с файла возвращаем его текст к исходному виду
                        self._reset_file_text(root_item, current_file_name)
                        self.selected_file = None
                        self.current_file_name = None

                self.batch_update = True
                
                if not item.parent():  # Корневой элемент файла
                    self.update_child_check_states(item, item.checkState(column))
                    self._update_all_layers_in_file(item, current_file_name)
                else:
                    layer_item = self._get_layer_item(item)
                    if layer_item:
                        layer_name = self._get_layer_name_from_item(layer_item)
                        self.update_child_check_states(item, item.checkState(column))
                        self.update_parent_check_states(item)
                        self.update_layer_statistics(layer_name, current_file_name)
                        
                        # Оповещаем об изменении конкретного слоя
                        if not self.updating_selection:
                            checked = layer_item.checkState(0) == Qt.Checked
                            self.layer_check_changed.emit(current_file_name, layer_name, checked)

                self.batch_update = False
                self.update_selection_count(current_file_name)
                # Оповещаем об изменении выбора
                if not self.updating_selection:
                    self.selection_changed.emit(current_file_name)
            else:
                Logger.log_message(self.lm.get_string("LOGGING", "invalid_file_name", root_item.text(0)))
                return
                
        except Exception as e:
            Logger.log_message(self.lm.get_string("LOGGING", "item_change_error", str(e)))
            return

    def _clear_file_statistics(self, file_name):
        """Очищает статистику для указанного файла"""
        if file_name in self.files_data:
            file_data = self.files_data[file_name]
            file_data['selected_entities'] = 0
            file_data['selected_layers'] = 0
            for layer_stats in file_data['layers'].values():
                layer_stats['selected'] = 0

    def _get_file_name_from_item(self, item):
        """Извлекает имя файла из элемента дерева"""
        # Получаем оригинальное имя файла из пользовательских данных
        if item.data(0, Qt.UserRole):
            return item.data(0, Qt.UserRole)
            
        text = item.text(0)
        # Handle connection error case
        error_text = self.lm.get_string("TREE_WIDGET_HANDLER", "error_receiving_data")
        if error_text and error_text in text:
            return text.split(f" ({error_text}")[0]
        
        # Handle regular file case
        file_text = self.lm.get_string("TREE_WIDGET_HANDLER", "file")
        if file_text and file_text in text:
            parts = text.split(file_text)
            if len(parts) > 1:
                file_part = parts[1]
                # Handle potential separator
                if " |" in file_part:
                    return file_part.split(" |")[0].strip()
                return file_part.strip()
        
        # If no standard format is detected, return the original text
        return text

    def _get_layer_name_from_item(self, item):
        """Извлекает имя слоя из элемента дерева"""
        # Получаем оригинальное имя слоя из пользовательских данных
        if item.data(0, Qt.UserRole):
            return item.data(0, Qt.UserRole)
            
        text = item.text(0)
        layer_prefix = self.lm.get_string("TREE_WIDGET_HANDLER", "layer")
        if layer_prefix in text:
            parts = text.split(layer_prefix)
            if len(parts) > 1:
                layer_part = parts[1]
                if " |" in layer_part:
                    return layer_part.split(" |")[0].strip()
                return layer_part.strip()
        return text.split('|')[0].replace(self.lm.get_string("TREE_WIDGET_HANDLER", "layer"), '').strip()

    def _get_layer_item(self, item):
        """Получает элемент слоя из любого дочернего элемента"""
        layer_item = item
        while layer_item.parent() and layer_item.parent().parent():
            layer_item = layer_item.parent()
        return layer_item if layer_item.parent() else None

    def _get_layer_data(self, file_name, layer_name):
        """Получает данные слоя по файлу и имени слоя"""
        if file_name in self.tree_items:
            return self.tree_items[file_name].get(layer_name)
        return None

    def update_child_check_states(self, parent_item, check_state):
        """Рекурсивно обновляет состояние дочерних элементов"""
        if not parent_item:
            return
            
        for i in range(parent_item.childCount()):
            child_item = parent_item.child(i)
            if check_state == Qt.PartiallyChecked:
                # Если родитель PartiallyChecked, дети сохраняют своё текущее состояние
                continue
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

        # Проверяем, существует ли уже элемент с таким именем файла
        existing_item = None
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            original_name = item.data(0, Qt.UserRole)
            if original_name and original_name == file_name:
                existing_item = item
                break

        # Если элемент существует, удаляем его
        if existing_item is not None:
            index = self.tree_widget.indexOfTopLevelItem(existing_item)
            self.tree_widget.takeTopLevelItem(index)
            if file_name in self.tree_items:
                del self.tree_items[file_name]
            if file_name in self.files_data:
                del self.files_data[file_name]

        # Initialize file-specific data
        self.files_data[file_name] = {
            'layers': {},
            'total_entities': self.total_entities,
            'selected_entities': 0,
            'layer_count': len(layers),
            'selected_layers': 0
        }

        # Initialize statistics
        for layer, entities in layers.items():
            self.layer_stats[layer] = {
                'total': len(entities),
                'selected': 0
            }
            self.files_data[file_name]['layers'][layer] = {
                'total': len(entities),
                'selected': 0
            }

        # Создаем элемент для file_name на вершине дерева с правильным склонением
        layers_word = get_word_form(self.layer_count, self.word_forms['layer'])
        entities_word = get_word_form(self.total_entities, self.word_forms['entity'])
        file_item = QTreeWidgetItem([
            self.lm.get_string("TREE_WIDGET_HANDLER", "file_text",
                             file_name, self.layer_count, layers_word,
                             self.total_entities, entities_word)
        ])
        
        # Сохраняем оригинальное имя файла в пользовательских данных
        file_item.setData(0, Qt.UserRole, file_name)
        
        file_item.setCheckState(0, Qt.Checked)  # Изначально файл отмечен галочкой
        self.tree_widget.addTopLevelItem(file_item)

        add_remove_button_to_item(file_item, self.tree_widget)

        # Отключаем обновления UI во время заполнения
        self.tree_widget.setUpdatesEnabled(False)

        # Initialize file structure
        self.tree_items[file_name] = {}

        for layer, entities in layers.items():
            entity_count = len(entities)
            # Используем локализованное сообщение для слоя
            layer_item = QTreeWidgetItem([
                self.lm.get_string("TREE_WIDGET_HANDLER", "layer_text",
                                 layer, entity_count, 
                                 get_word_form(entity_count, self.word_forms['entity']),
                                 0, self.word_forms['entity'][2])
            ])
            
            # Сохраняем оригинальное имя слоя в пользовательских данных
            layer_item.setData(0, Qt.UserRole, layer)
            
            layer_item.setCheckState(0, Qt.Unchecked)
            file_item.addChild(layer_item)
            
            self.tree_items[file_name][layer] = {'item': layer_item, 'entities': {}}

            entity_items = []
            for entity in entities:
                entity_description = f"{entity}"
                entity_item = QTreeWidgetItem([entity_description])
                entity_item.setCheckState(0, Qt.Unchecked)
                entity_items.append(entity_item)
                self.tree_items[file_name][layer]['entities'][entity_description] = entity_item

            layer_item.addChildren(entity_items)

            # Отложенное добавление атрибутов
            for entity, entity_item in zip(entities, entity_items):
                self.add_entity_attributes_and_geometry(entity_item, entity)
        self.handle_item_changed(file_item, 0)  # Обновляем состояние корневого элемента

        self.tree_widget.setUpdatesEnabled(True)
        # Уведомляем о создании нового файла в дереве
        self.tree_structure_created.emit(file_name, layers)

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
            'ELLIPSE': ["center", "major_axis", "extrusion", "ratio", "start_param", "end_param"],
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

        attr_header = QTreeWidgetItem([self.lm.get_string("TREE_WIDGET_HANDLER", "attributes")])
        attr_header.setCheckState(0, Qt.Unchecked)
        entity_item.addChild(attr_header)
        geometry_header = QTreeWidgetItem([self.lm.get_string("TREE_WIDGET_HANDLER", "geometry")])
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
        """Выбирает сущности в дереве и обновляет selected_entities"""
        self.updating_selection = True  # Устанавливаем флаг программного обновления
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
        progress_dialog = QProgressDialog(
            self.lm.get_string("TREE_WIDGET_HANDLER", "checking_objects"),
            self.lm.get_string("TREE_WIDGET_HANDLER", "cancel"),
            0, total_steps
        )
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.show()

        processed = 0
        current_file = self.get_selected_file_name()
        if not current_file:
            return

        # Обновляем статистику для файла перед обработкой
        if current_file in self.files_data:
            self._clear_file_statistics(current_file)

        for layer_name, layer_entities in layers_to_check.items():
            layer_data = self._get_layer_data(current_file, layer_name)
            if layer_data:
                # Массовое обновление элементов слоя
                for entity in layer_entities:
                    entity_description = f"{entity}"
                    if entity_description in layer_data['entities']:
                        entity_item = layer_data['entities'][entity_description]
                        entity_item.setCheckState(0, Qt.Checked)
                        self.update_parent_check_states(entity_item)
                
                # Обновляем статистику слоя
                self.update_layer_statistics(layer_name, current_file)
                
                processed += len(layer_entities)
                progress_dialog.setValue(processed)
                QgsApplication.processEvents()

                if progress_dialog.wasCanceled():
                    break

        progress_dialog.close()
        
        self.selectable = False
        self.batch_update = False
        self.tree_widget.setUpdatesEnabled(True)

        # Обновляем общую статистику и текст файла
        self.update_selection_count(current_file)
        if self.selected_file:
            self._update_file_text(current_file)
            # После завершения всех обновлений эмитим сигнал один раз
            self.updating_selection = False  # Сбрасываем флаг

    def clear_all_checks(self):
        self.batch_update = True
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            item.setCheckState(0, Qt.Unchecked)
            self.update_child_check_states(item, Qt.Unchecked)
        self.batch_update = False
        self.update_selection_count()

    def update_selection_count(self, file_name=None):
        """Обновляет информацию о выбранных слоях и объектах"""
        if not file_name or not self.selected_file:
            return

        if file_name not in self.files_data:
            return

        file_data = self.files_data[file_name]
        
        self.selected_layers_count = 0
        self.selected_total_entities = 0

        # Обновляем статистику только для активного файла
        for layer_name, layer_stats in file_data['layers'].items():
            if layer_name in self.tree_items[file_name]:
                layer_item = self.tree_items[file_name][layer_name]['item']
                if layer_item.checkState(0) in [Qt.Checked, Qt.PartiallyChecked]:
                    self.selected_layers_count += 1
                
                selected = sum(1 for entity_item in self.tree_items[file_name][layer_name]['entities'].values()
                             if entity_item.checkState(0) == Qt.Checked)
                self.selected_total_entities += selected
                layer_stats['selected'] = selected

        # Обновляем статистику на уровне файла
        file_data['selected_layers'] = self.selected_layers_count
        file_data['selected_entities'] = self.selected_total_entities

        self._update_file_text(file_name)

    def _update_file_text(self, file_name):
        """Обновляет текст в заголовке файла"""
        if not self.selected_file:
            return

        file_data = self.files_data.get(file_name)
        if not file_data:
            return
            
        layers_word = get_word_form(file_data['layer_count'], self.word_forms['layer'])
        selected_layers_word = get_word_form(self.selected_layers_count, self.word_forms['layer'])
        entities_word = get_word_form(file_data['total_entities'], self.word_forms['entity'])
        selected_entities_word = get_word_form(self.selected_total_entities, self.word_forms['entity'])
        
        if self.selected_layers_count > 0:
            self.selected_file.setText(0, (
                f'{self.lm.get_string("TREE_WIDGET_HANDLER", "file")} {file_name} | ({file_data["layer_count"]} {layers_word} | '
                f'{self.lm.get_string("TREE_WIDGET_HANDLER", "selected")} {self.selected_layers_count} {selected_layers_word} | '
                f'{self.selected_total_entities} {selected_entities_word} из {file_data["total_entities"]})'
            ))
        else:
            self.selected_file.setText(0, 
                f'{self.lm.get_string("TREE_WIDGET_HANDLER", "file")} {file_name} | ({file_data["layer_count"]} {layers_word}, {file_data["total_entities"]} {entities_word})'
            )

    def update_layer_statistics(self, layer_name, file_name):
        """Обновляет статистику выбранных объектов для слоя"""
        layer_data = self._get_layer_data(file_name, layer_name)
        if layer_data and file_name in self.files_data:
            layer_item = layer_data['item']
            
            total_entities = len(layer_data['entities'])
            selected_entities = sum(
                1 for entity_item in layer_data['entities'].values()
                if entity_item.checkState(0) == Qt.Checked
            )
            
            # Update file-specific statistics
            self.files_data[file_name]['layers'][layer_name] = {
                'total': total_entities,
                'selected': selected_entities
            }
            
            # Обновляем текст элемента слоя с правильным склонением
            entities_word = get_word_form(total_entities, self.word_forms['entity'])
            selected_entities_word = get_word_form(selected_entities, self.word_forms['entity'])
            
            layer_item.setText(0, (
                f'{self.lm.get_string("TREE_WIDGET_HANDLER", "layer")} {layer_name} | ({total_entities} {entities_word} | '
                f'{self.lm.get_string("TREE_WIDGET_HANDLER", "selected")} {selected_entities} {selected_entities_word})'
            ))

    def get_selected_file_name(self):
        """Возвращает имя выбранного файла или None"""
        if self.selected_file:
            # Получаем оригинальное имя файла из пользовательских данных
            original_name = self.selected_file.data(0, Qt.UserRole)
            if original_name:
                Logger.log_message(self.lm.get_string("LOGGING", "selected_file", original_name))
                return original_name
                
            # Запасной вариант - парсинг текста
            file_text = self.selected_file.text(0)
            file_name = file_text.split(self.lm.get_string("TREE_WIDGET_HANDLER", "file"))[1].split(' |')[0]
            Logger.log_message(self.lm.get_string("LOGGING", "selected_file", file_name))
            return file_name
        return None

    def _update_all_layers_in_file(self, file_item, file_name):
        """Обновляет статистику для всех слоев в файле"""
        if not file_item or not file_name:
            return
            
        for i in range(file_item.childCount()):
            layer_item = file_item.child(i)
            if not layer_item:
                continue
            layer_name = self._get_layer_name_from_item(layer_item)
            if layer_name and layer_name in self.tree_items[file_name]:
                self.update_layer_statistics(layer_name, file_name)
    
    def set_layer_check_state(self, file_name, layer_name, checked):
        """
        Устанавливает состояние checkbox для конкретного слоя программно.
        Используется для синхронизации с QGIS.
        
        Args:
            file_name: Имя файла
            layer_name: Имя слоя
            checked: Состояние (True/False)
        """
        if file_name in self.tree_items:
            layer_data = self.tree_items[file_name].get(layer_name)
            if layer_data and 'item' in layer_data:
                layer_item = layer_data['item']
                # Устанавливаем флаг, что это программное обновление
                self.updating_selection = True
                try:
                    layer_item.setCheckState(0, Qt.Checked if checked else Qt.Unchecked)
                    # Обновляем состояние родительского узла (файла)
                    self.update_parent_check_states(layer_item)
                    # Обновляем статистику
                    self.update_layer_statistics(layer_name, file_name)
                    # Обновляем общую статистику файла
                    self.update_selection_count(file_name)
                finally:
                    self.updating_selection = False
    
    def get_layer_check_state(self, file_name, layer_name):
        """
        Получает состояние checkbox для конкретного слоя.
        
        Args:
            file_name: Имя файла
            layer_name: Имя слоя
            
        Returns:
            bool: True если выбран, False если нет, None если не найден
        """
        if file_name in self.tree_items:
            layer_data = self.tree_items[file_name].get(layer_name)
            if layer_data and 'item' in layer_data:
                layer_item = layer_data['item']
                return layer_item.checkState(0) == Qt.Checked
        return None
