from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import QgsProject, QgsLayerTreeGroup, QgsLayerTreeLayer
from ..logger.logger import Logger
from ..localization.localization_manager import LocalizationManager


class QGISLayerSyncManager(QObject):
    """
    Менеджер синхронизации между деревом плагина и панелью слоев QGIS.
    Обеспечивает двустороннюю синхронизацию состояния checkbox-ов.
    """
    
    # Сигналы для оповещения об изменениях
    plugin_tree_changed = pyqtSignal(str, str, bool)  # file_name, layer_name, checked
    qgis_tree_changed = pyqtSignal(str, str, bool)    # file_name, layer_name, checked
    
    def __init__(self, tree_widget_handler):
        super().__init__()
        self.tree_widget_handler = tree_widget_handler
        self.lm = LocalizationManager.instance()
        self.project = QgsProject.instance()
        self.layer_tree = self.project.layerTreeRoot()
        
        # Словарь для отслеживания соответствий между плагином и QGIS
        # Структура: {file_name: {layer_name: qgis_layer_tree_node}}
        self.sync_mapping = {}
        
        # Флаг для предотвращения рекурсивных обновлений
        self.updating = False
          # Подключение к сигналам изменения состояния в QGIS
        self.layer_tree.visibilityChanged.connect(self.on_qgis_visibility_changed)
        
        # Подключение к сигналам дерева плагина
        if self.tree_widget_handler:
            self.tree_widget_handler.selection_changed.connect(self.on_plugin_tree_changed)
    
    def extract_file_name_from_group(self, group_name):
        """
        Извлекает имя файла из названия группы QGIS.
        Отрезает часть после '_' как указано в требованиях.
        Пример: "аппаора.dxf_GPKG(byLay)" -> "аппаора.dxf"
        """
        if '_' in group_name:
            return group_name.split('_')[0]
        return group_name
    
    def create_qgis_group_structure(self, file_name, layers_dict):
        """
        Привязывает синхронизацию к уже существующим группам в QGIS, созданным подплагином.
        
        Args:
            file_name: Имя DXF файла
            layers_dict: Словарь слоев {layer_name: entities}
        """
        if self.updating:
            return
            
        try:
            self.updating = True
            
            # Отрезаем часть после _ в имени файла для QGIS (как указано в требованиях)
            qgis_file_name = self.extract_file_name_from_group(file_name)
            
            # Ищем существующую группу файла в QGIS
            file_group = self._find_group_by_name(qgis_file_name)
            
            if not file_group:
                Logger.log_warning(f"Группа файла '{qgis_file_name}' не найдена в QGIS")
                return
            
            # Ищем существующие группы слоев
            layer_nodes = {}
            for layer_name in layers_dict.keys():
                layer_group = self._find_child_group_by_name(file_group, layer_name)
                if layer_group:
                    layer_nodes[layer_name] = layer_group
                    # Подключаем сигнал изменения видимости для каждого слоя
                    layer_group.visibilityChanged.connect(self.on_qgis_visibility_changed)
                else:
                    Logger.log_warning(f"Группа слоя '{layer_name}' не найдена в группе '{qgis_file_name}'")
            
            # Подключаем сигнал изменения видимости для группы файла
            file_group.visibilityChanged.connect(self.on_qgis_visibility_changed)
            
            # Сохраняем соответствие для синхронизации (используем оригинальное имя файла)
            self.sync_mapping[file_name] = {
                'file_group': file_group,
                'layers': layer_nodes
            }
            
            Logger.log_message(f"Привязана синхронизация к группе QGIS для файла {file_name} ({qgis_file_name}) с {len(layer_nodes)} слоями")
            
        except Exception as e:
            Logger.log_error(f"Ошибка привязки синхронизации к QGIS: {str(e)}")
        finally:
            self.updating = False
    
    def _find_group_by_name(self, group_name):
        """
        Ищет группу по имени в корне дерева слоев QGIS.
        
        Args:
            group_name: Имя группы для поиска
            
        Returns:
            QgsLayerTreeGroup или None если не найдено
        """
        for child in self.layer_tree.children():
            if isinstance(child, QgsLayerTreeGroup) and child.name() == group_name:
                return child
        return None
    
    def _find_child_group_by_name(self, parent_group, group_name):
        """
        Ищет дочернюю группу по имени в родительской группе.
        
        Args:
            parent_group: Родительская группа
            group_name: Имя дочерней группы для поиска
            
        Returns:
            QgsLayerTreeGroup или None если не найдено
        """
        for child in parent_group.children():
            if isinstance(child, QgsLayerTreeGroup) and child.name() == group_name:
                return child
        return None


    def sync_from_qgis_to_plugin(self, file_name, layer_name, checked):
        """
        Синхронизирует состояние от дерева QGIS к дереву плагина.
        
        Args:
            file_name: Имя файла
            layer_name: Имя слоя
            checked: Состояние checkbox (True/False)
        """
        if self.updating:
            return
            
        try:
            self.updating = True
            
            # Обновляем состояние в дереве плагина
            if self.tree_widget_handler:
                self.tree_widget_handler.set_layer_check_state(file_name, layer_name, checked)
            
            Logger.log_message(f"Синхронизация QGIS->плагин: {file_name}/{layer_name} = {checked}")            
        except Exception as e:
            Logger.log_error(f"Ошибка синхронизации QGIS->плагин: {str(e)}")
        finally:
            self.updating = False
    
    def _update_file_group_state(self, file_group, file_name):
        """
        Обновляет состояние группы файла на основе состояния дочерних слоев.
        """
        if not file_group:
            return
            
        child_count = 0
        checked_count = 0
        
        for child in file_group.children():
            if isinstance(child, QgsLayerTreeGroup):
                child_count += 1
                if child.itemVisibilityChecked():
                    checked_count += 1        
        if child_count == 0:
            return
            
        # Устанавливаем состояние группы файла
        if checked_count == child_count:
            file_group.setItemVisibilityChecked(True)
        elif checked_count > 0:
            # Частично выбрано - в QGIS нет поддержки PartiallyChecked для групп
            file_group.setItemVisibilityChecked(True)
        else:
            file_group.setItemVisibilityChecked(False)
    
    def on_qgis_visibility_changed(self, node):
        """
        Обработчик изменения видимости слоя/группы в QGIS.
        
        Args:
            node: QgsLayerTreeNode - узел дерева, состояние которого изменилось
        """
        if self.updating:
            return
            
        try:
            # Получаем состояние видимости из узла
            is_checked = node.itemVisibilityChecked()
            
            # Ищем соответствующий файл и слой
            for file_name, mapping in self.sync_mapping.items():
                # Проверяем, является ли это группой файла
                if mapping.get('file_group') == node:
                    # Изменилась видимость группы файла - обновляем все слои
                    self._sync_file_group_change(file_name, is_checked)
                    return
                
                # Проверяем, является ли это группой слоя
                for layer_name, layer_node in mapping.get('layers', {}).items():
                    if layer_node == node:
                        # Изменилась видимость конкретного слоя
                        self.sync_from_qgis_to_plugin(file_name, layer_name, is_checked)
                        return
                        
        except Exception as e:
            Logger.log_error(f"Ошибка обработки изменения видимости QGIS: {str(e)}")
    
    def _sync_file_group_change(self, file_name, checked):
        """
        Синхронизирует изменение состояния группы файла.
        """
        if file_name in self.sync_mapping:
            mapping = self.sync_mapping[file_name]
            
            # Обновляем все слои в группе
            for layer_name, layer_node in mapping['layers'].items():
                layer_node.setItemVisibilityChecked(checked)
                self.sync_from_qgis_to_plugin(file_name, layer_name, checked)
    
    def on_plugin_tree_changed(self, file_name):
        """
        Обработчик изменения состояния в дереве плагина.
        """
        if self.updating:
            return
            
        try:
            # Получаем актуальное состояние слоев из дерева плагина
            if file_name in self.tree_widget_handler.tree_items:
                file_data = self.tree_widget_handler.tree_items[file_name]
                
                for layer_name, layer_info in file_data.items():
                    if 'item' in layer_info:
                        layer_item = layer_info['item']
                        checked = layer_item.checkState(0) == 2  # Qt.Checked = 2
                        
                        # Синхронизируем конкретный слой
                        self.sync_layer_from_plugin_to_qgis(file_name, layer_name, checked)
                        
        except Exception as e:
            Logger.log_error(f"Ошибка обработки изменения дерева плагина: {str(e)}")
    
    def sync_layer_from_plugin_to_qgis(self, file_name, layer_name, checked):
        """
        Синхронизирует конкретный слой от дерева плагина к дереву QGIS.
        """
        if self.updating:
            return
            
        try:
            self.updating = True
            
            if file_name in self.sync_mapping:
                mapping = self.sync_mapping[file_name]
                
                # Обновляем состояние слоя
                if layer_name in mapping['layers']:
                    layer_node = mapping['layers'][layer_name]
                    layer_node.setItemVisibilityChecked(checked)
                
                # Обновляем состояние группы файла
                file_group = mapping['file_group']
                self._update_file_group_state(file_group, file_name)
                
                Logger.log_message(f"Синхронизация слоя плагин->QGIS: {file_name}/{layer_name} = {checked}")
                
        except Exception as e:
            Logger.log_error(f"Ошибка синхронизации слоя плагин->QGIS: {str(e)}")
        finally:
            self.updating = False

    def remove_file_from_sync(self, file_name):
        """
        Удаляет файл из синхронизации и из дерева QGIS.
        """
        if file_name in self.sync_mapping:
            try:
                # Удаляем группу из дерева QGIS
                file_group = self.sync_mapping[file_name]['file_group']
                if file_group:
                    parent = file_group.parent()
                    if parent:
                        parent.removeChildNode(file_group)
                
                # Удаляем из маппинга
                del self.sync_mapping[file_name]
                
                Logger.log_message(f"Файл {file_name} удален из синхронизации")
                
            except Exception as e:
                Logger.log_error(f"Ошибка удаления файла из синхронизации: {str(e)}")
    
    def clear_all_sync(self):
        """
        Очищает всю синхронизацию.
        """
        for file_name in list(self.sync_mapping.keys()):
            self.remove_file_from_sync(file_name)
