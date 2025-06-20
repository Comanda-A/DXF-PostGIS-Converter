from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox
from qgis.PyQt.QtCore import Qt
from ..localization.localization_manager import LocalizationManager
from ..logger.logger import Logger


class SchemaSelectorDialog(QDialog):
    """
    Диалог для выбора схемы при отсутствии файлов в базе данных
    """
    
    def __init__(self, schemas, parent=None):
        """
        Инициализация диалога выбора схемы
        
        Args:
            schemas: Список доступных схем
            parent: Родительский виджет
        """
        super().__init__(parent)
        self.schemas = schemas
        self.lm = LocalizationManager.instance()
        self.selected_schema = None
        
        self.setWindowTitle(self.lm.get_string("MAIN_DIALOG", "schema_selector_title"))
        
        # Настройки окна для правильного отображения поверх главного окна
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        
        self.setMinimumWidth(400)
        self.setup_ui()
        self.load_schemas()
        
        # Центрируем диалог относительно родительского окна
        if parent:
            self.move(parent.geometry().center() - self.rect().center())
    
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        layout = QVBoxLayout(self)
        
        # Информационный текст
        info_label = QLabel(self.lm.get_string("MAIN_DIALOG", "schema_selector_info"))
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Выпадающий список схем
        schema_layout = QHBoxLayout()
        schema_label = QLabel(self.lm.get_string("MAIN_DIALOG", "schema_selector_label"))
        self.schema_combo = QComboBox()
        self.schema_combo.setMinimumWidth(200)
        
        schema_layout.addWidget(schema_label)
        schema_layout.addWidget(self.schema_combo)
        layout.addLayout(schema_layout)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        self.ok_button = QPushButton(self.lm.get_string("COMMON", "ok"))
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setEnabled(False)  # Изначально отключена
        
        self.cancel_button = QPushButton(self.lm.get_string("COMMON", "cancel"))
        self.cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.ok_button)
        buttons_layout.addWidget(self.cancel_button)
        
        layout.addLayout(buttons_layout)
        
        # Подключаем обработчик изменения выбора
        self.schema_combo.currentTextChanged.connect(self.on_schema_changed)
    
    def load_schemas(self):
        """Загрузка списка схем в интерфейс"""
        try:
            if not self.schemas:
                QMessageBox.warning(
                    self,
                    self.lm.get_string("MAIN_DIALOG", "warning_title"),
                    self.lm.get_string("MAIN_DIALOG", "no_schemas_available")
                )
                self.reject()
                return
            
            self.schema_combo.clear()
            self.schema_combo.addItem("")  # Пустой элемент
            self.schema_combo.addItems(self.schemas)
            
        except Exception as e:
            Logger.log_error(f"Ошибка при загрузке схем в интерфейс: {str(e)}")
            QMessageBox.critical(
                self,
                self.lm.get_string("MAIN_DIALOG", "error_title"),
                self.lm.get_string("MAIN_DIALOG", "schema_load_error")
            )
            self.reject()
    
    def on_schema_changed(self, schema_name):
        """Обработчик изменения выбранной схемы"""
        self.ok_button.setEnabled(bool(schema_name.strip()))
    
    def accept(self):
        """Обработчик нажатия кнопки OK"""
        self.selected_schema = self.schema_combo.currentText().strip()
        if self.selected_schema:
            super().accept()
    
    def get_selected_schema(self):
        """Возвращает выбранную схему"""
        return self.selected_schema
    
    def showEvent(self, event):
        """Обработчик события показа диалога"""
        super().showEvent(event)
        
        # Убеждаемся, что диалог отображается поверх всех окон
        self.raise_()
        self.activateWindow()
        
        # Центрируем диалог на экране, если нет родительского окна
        if not self.parent():
            self.center_on_screen()
    
    def center_on_screen(self):
        """Центрирует диалог на экране"""
        try:
            from qgis.PyQt.QtWidgets import QApplication
            
            screen = QApplication.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()
                dialog_geometry = self.geometry()
                
                x = (screen_geometry.width() - dialog_geometry.width()) // 2
                y = (screen_geometry.height() - dialog_geometry.height()) // 2
                
                self.move(x, y)
        except Exception as e:
            Logger.log_error(f"Ошибка при центрировании диалога: {str(e)}")
    
    def exec_(self):
        """Переопределяем exec_ для дополнительных настроек отображения"""
        # Убеждаемся, что диалог будет поверх всех окон
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.raise_()
        self.activateWindow()
        
        return super().exec_()
