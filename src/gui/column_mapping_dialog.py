from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                           QLabel, QPushButton, QComboBox, QTableWidget, 
                           QTableWidgetItem, QCheckBox, QGroupBox, QMessageBox,
                           QHeaderView, QAbstractItemView)
from PyQt5.QtCore import Qt, pyqtSignal
from qgis.core import QgsSettings

from ..localization.localization_manager import LocalizationManager
from ..logger.logger import Logger


class ColumnMappingDialog(QDialog):
    """
    Диалог для настройки сопоставления столбцов между стандартными полями DXF-таблиц и существующими таблицами БД
    """
    
    # Стратегии сопоставления
    STRATEGY_MAPPING_ONLY = "mapping_only"  # Только сопоставление
    STRATEGY_MAPPING_ADD_COLUMNS = "mapping_add_columns"  # Сопоставление + добавление полей
    STRATEGY_MAPPING_BACKUP = "mapping_backup"  # Сопоставление + backup таблица
    STRATEGY_MAPPING_ADD_BACKUP = "mapping_add_backup"  # Сопоставление + добавление полей + backup
    
    mapping_configured = pyqtSignal(dict)  # Сигнал с настройками сопоставления
    
    def __init__(self, db_connection_params, layer_schema, existing_tables=None, parent=None):
        """
        Инициализация диалога сопоставления столбцов
        
        :param db_connection_params: Параметры подключения к БД
        :param layer_schema: Схема для поиска таблиц
        :param existing_tables: Список существующих таблиц с конфликтами структуры (опционально)
        :param parent: Родительский виджет
        """
        super().__init__(parent)
        self.db_connection_params = db_connection_params
        self.layer_schema = layer_schema
        self.existing_tables = existing_tables or []
        self.db_columns = []
        self.column_mappings = {}
        
        # Стандартная структура DXF таблицы слоя
        self.dxf_default_columns = {
            'id': 'INTEGER PRIMARY KEY',
            'file_id': 'INTEGER',
            'geometry': 'GEOMETRY(GEOMETRYZ, 4326)',
            'geom_type': 'VARCHAR',
            'notes': 'TEXT',
            'extra_data': 'JSONB'
        }
        
        self.lm = LocalizationManager.instance()
        
        self.setWindowTitle("Настройка сопоставления столбцов DXF таблиц")
        self.setMinimumSize(800, 600)
        
        self.setup_ui()
        self.load_existing_tables()        
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        layout = QVBoxLayout(self)
        
        # Информационная панель
        info_group = QGroupBox("Информация")
        info_layout = QVBoxLayout()
        info_label = QLabel(
            "Стандартная структура DXF таблицы слоя будет создана со следующими столбцами:\n"
            "• id (INTEGER) - Первичный ключ\n"
            "• file_id (INTEGER) - Ссылка на файл\n"
            "• geometry (GEOMETRY) - Геометрия объекта\n"
            "• geom_type (VARCHAR) - Тип геометрии\n"
            "• notes (TEXT) - Примечания\n"
            "• extra_data (JSONB) - Дополнительные данные\n\n"
            "Если в БД уже существуют таблицы с такими же именами, но другой структурой,\n"
            "настройте сопоставление столбцов ниже."
        )
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Группа выбора стратегии
        strategy_group = QGroupBox("Стратегия сопоставления")
        strategy_layout = QVBoxLayout()
        
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItem("Только сопоставление столбцов", self.STRATEGY_MAPPING_ONLY)
        self.strategy_combo.addItem("Сопоставление + добавление недостающих полей", self.STRATEGY_MAPPING_ADD_COLUMNS)
        self.strategy_combo.addItem("Сопоставление + создание backup таблицы", self.STRATEGY_MAPPING_BACKUP)
        self.strategy_combo.addItem("Сопоставление + добавление полей + backup", self.STRATEGY_MAPPING_ADD_BACKUP)
        
        strategy_layout.addWidget(QLabel("Выберите стратегию:"))
        strategy_layout.addWidget(self.strategy_combo)
        strategy_group.setLayout(strategy_layout)
        layout.addWidget(strategy_group)
        
        # Группа выбора таблицы для сопоставления
        table_group = QGroupBox("Выбор таблицы для сопоставления")
        table_layout = QVBoxLayout()
        
        self.table_combo = QComboBox()
        self.table_combo.currentTextChanged.connect(self.on_table_selected)
        
        table_layout.addWidget(QLabel("Выберите существующую таблицу:"))
        table_layout.addWidget(self.table_combo)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)
        
        # Группа настройки сопоставления
        mapping_group = QGroupBox("Настройка сопоставления столбцов")
        mapping_layout = QVBoxLayout()
        
        # Таблица сопоставления
        self.mapping_table = QTableWidget()
        self.mapping_table.setColumnCount(5)
        self.mapping_table.setHorizontalHeaderLabels([
            "Столбец DXF (стандарт)", "Тип DXF", "Столбец БД", "Тип БД", "Создать новый"
        ])
        
        # Настройка таблицы
        header = self.mapping_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        self.mapping_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        mapping_layout.addWidget(self.mapping_table)
        mapping_group.setLayout(mapping_layout)
        layout.addWidget(mapping_group)
        
        # Кнопки
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.auto_map_button = QPushButton("Автосопоставление")
        self.auto_map_button.clicked.connect(self.auto_map_columns)
        button_layout.addWidget(self.auto_map_button)
        
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.ok_button = QPushButton("Применить")
        self.ok_button.clicked.connect(self.apply_mapping)
        
        button_layout.addWidget(self.ok_button)
        
        layout.addLayout(button_layout)
        
        # Заполняем таблицу со стандартной структурой DXF
        self.populate_mapping_table()
        
    def load_existing_tables(self):
        """Загрузка списка существующих таблиц в схеме"""
        try:
            # Импортируем здесь для избежания циклического импорта
            from ..db.database import get_tables_in_schema
            
            tables = get_tables_in_schema(
                self.db_connection_params['username'],
                self.db_connection_params['password'], 
                self.db_connection_params['address'],
                self.db_connection_params['port'],
                self.db_connection_params['dbname'],
                self.layer_schema
            )
            
            self.table_combo.clear()
            self.table_combo.addItem("-- Выберите таблицу --", "")
            
            for table in tables:
                self.table_combo.addItem(table, table)
                
            Logger.log_message(f"Загружены таблицы схемы {self.layer_schema}: {tables}")
        except Exception as e:
            Logger.log_error(f"Ошибка загрузки таблиц схемы: {str(e)}")
            
    def on_table_selected(self, table_name):
        """Обработчик выбора таблицы"""
        if table_name and table_name != "-- Выберите таблицу --":
            self.load_db_columns_for_table(table_name)
            self.populate_mapping_table()
        else:
            self.db_columns = []
            self.populate_mapping_table()
            
    def load_db_columns_for_table(self, table_name):
        """Загрузка столбцов из выбранной существующей таблицы БД"""
        try:
            # Импортируем здесь для избежания циклического импорта
            from ..db.database import get_table_columns
            
            self.db_columns = get_table_columns(
                self.db_connection_params['username'],
                self.db_connection_params['password'], 
                self.db_connection_params['address'],
                self.db_connection_params['port'],
                self.db_connection_params['dbname'],
                table_name,
                self.layer_schema
            )
            Logger.log_message(f"Загружены столбцы таблицы {table_name}: {self.db_columns}")
        except Exception as e:
            Logger.log_error(f"Ошибка загрузки столбцов таблицы: {str(e)}")
            self.db_columns = []            
    
    def populate_mapping_table(self):
        """Заполнение таблицы сопоставления"""
        # Очищаем таблицу перед заполнением
        self.mapping_table.clear()
        self.mapping_table.setRowCount(len(self.dxf_default_columns))
        self.mapping_table.setHorizontalHeaderLabels([
            "Столбец DXF (стандарт)", "Тип DXF", "Столбец БД", "Тип БД", "Создать новый"
        ])
        
        for row, (dxf_column, column_type) in enumerate(self.dxf_default_columns.items()):
            # DXF поле (стандартная структура)
            dxf_item = QTableWidgetItem(dxf_column)
            dxf_item.setFlags(Qt.ItemIsEnabled)
            self.mapping_table.setItem(row, 0, dxf_item)
            
            # Тип DXF поля
            type_item = QTableWidgetItem(column_type)
            type_item.setFlags(Qt.ItemIsEnabled)
            self.mapping_table.setItem(row, 1, type_item)
            
            # Комбобокс для выбора столбца БД
            db_combo = QComboBox()
            db_combo.addItem("-- Не сопоставлять --", "")
            
            for db_column in self.db_columns:
                display_text = f"{db_column['name']} ({db_column['type']})"
                db_combo.addItem(display_text, db_column['name'])
            
            self.mapping_table.setCellWidget(row, 2, db_combo)
            
            # Тип столбца БД (будет обновляться при выборе)
            db_type_item = QTableWidgetItem("")
            db_type_item.setFlags(Qt.ItemIsEnabled)
            self.mapping_table.setItem(row, 3, db_type_item)
            
            # Подключаем сигнал изменения выбора в комбобоксе
            db_combo.currentTextChanged.connect(
                lambda text, r=row: self.update_db_type_column(r, text)
            )
            
            # Чекбокс для создания нового столбца
            create_checkbox = QCheckBox()
            create_checkbox.setChecked(False)
            self.mapping_table.setCellWidget(row, 4, create_checkbox)
            
    def update_db_type_column(self, row, selected_text):
        """Обновляет отображение типа столбца БД при выборе в комбобоксе"""
        db_type_item = self.mapping_table.item(row, 3)
        if db_type_item is None:
            db_type_item = QTableWidgetItem("")
            db_type_item.setFlags(Qt.ItemIsEnabled)
            self.mapping_table.setItem(row, 3, db_type_item)
        
        if "-- Не сопоставлять --" in selected_text:
            db_type_item.setText("")
        else:
            # Извлекаем тип из строки формата "column_name (column_type)"
            if "(" in selected_text and ")" in selected_text:
                type_part = selected_text.split("(")[1].split(")")[0]
                db_type_item.setText(type_part)
            else:
                # Ищем тип в списке db_columns
                combo = self.mapping_table.cellWidget(row, 2)
                selected_column = combo.currentData()
                for db_column in self.db_columns:
                    if db_column['name'] == selected_column:
                        db_type_item.setText(db_column['type'])
                        break
                else:
                    db_type_item.setText("")
            
    def auto_map_columns(self):
        """Автоматическое сопоставление столбцов по именам"""
        for row in range(self.mapping_table.rowCount()):
            dxf_column = self.mapping_table.item(row, 0).text().lower()
            db_combo = self.mapping_table.cellWidget(row, 2)
              # Ищем точное совпадение
            for i in range(db_combo.count()):
                item_data = db_combo.itemData(i)
                if item_data and item_data.lower() == dxf_column:
                    db_combo.setCurrentIndex(i)
                    break
            else:
                # Ищем частичное совпадение
                for i in range(db_combo.count()):
                    item_data = db_combo.itemData(i)
                    if item_data:
                        db_column = item_data.lower()
                        if dxf_column in db_column or db_column in dxf_column:
                            db_combo.setCurrentIndex(i)
                            break
                        
        Logger.log_message("Выполнено автоматическое сопоставление столбцов")
        
    def apply_mapping(self):
        """Применение настроек сопоставления"""
        strategy = self.strategy_combo.currentData()
        selected_table = self.table_combo.currentData()
        
        if not selected_table:
            QMessageBox.warning(
                self,
                "Предупреждение", 
                "Выберите таблицу для сопоставления"
            )
            return
        mappings = {}
        new_columns = []
        
        for row in range(self.mapping_table.rowCount()):
            dxf_column = self.mapping_table.item(row, 0).text()
            db_combo = self.mapping_table.cellWidget(row, 2)
            create_checkbox = self.mapping_table.cellWidget(row, 4)
            
            db_column = db_combo.currentData()
            create_new = create_checkbox.isChecked()
            
            if db_column:
                mappings[dxf_column] = db_column
            elif create_new:
                new_columns.append(dxf_column)
                
        # Проверяем корректность настроек
        if strategy == self.STRATEGY_MAPPING_ONLY and new_columns:
            QMessageBox.warning(
                self,
                "Предупреждение",
                "В режиме 'Только сопоставление' нельзя создавать новые столбцы"
            )
            return
            
        mapping_config = {
            'strategy': strategy,
            'mappings': mappings,
            'new_columns': new_columns,
            'target_table': selected_table,
            'layer_schema': self.layer_schema,
            'dxf_structure': self.dxf_default_columns
        }
        
        Logger.log_message(f"Настройки сопоставления: {mapping_config}")
        
        # Сохраняем настройки
        self.save_mapping_settings(mapping_config)
        
        self.mapping_configured.emit(mapping_config)
        self.accept()        
    def save_mapping_settings(self, config):
        """Сохранение настроек сопоставления"""
        settings = QgsSettings()
        settings.setValue(f"DXFPostGIS/columnMapping/strategy", config['strategy'])
        settings.setValue(f"DXFPostGIS/columnMapping/mappings", config['mappings'])
        settings.setValue(f"DXFPostGIS/columnMapping/newColumns", config['new_columns'])
        settings.setValue(f"DXFPostGIS/columnMapping/targetTable", config['target_table'])
