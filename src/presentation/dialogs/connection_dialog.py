
import os
import inject

from PyQt5.QtWidgets import QMessageBox, QDialog
from qgis.PyQt import uic

from ...application.dtos import ConnectionConfigDTO
from ...application.interfaces import ILocalization
from ...application.services import ConnectionConfigService
from ...application.database import DBSession
from ...presentation.services import DialogTranslator


# Load UI file from resources
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), '.', 'resources', 'connection_dialog.ui'))

class ConnectionDialog(QDialog, FORM_CLASS):
    
    @inject.autoparams('connection_service', 'session', 'localization')
    def __init__(
        self,
        parent,
        connection_service: ConnectionConfigService,
        session: DBSession,
        localization: ILocalization
    ):
        """Constructor."""
        super().__init__(parent)
        self.setupUi(self)

        self._connection_service = connection_service
        self._session = session
        self._localization = localization
        
        # Инициализация компонентов
        self._init_components()
        self._connect_signals()
        self._setup_ui()
    
    def tr(self, key: str, *args) -> str:
        """Перевод строки с использованием ILocalization."""
        translated = self._localization.tr("CONNECTION_DIALOG", key, *args)
        return translated

    def _init_components(self):
        """Загрузка настроек."""
        self.dbms_combo.addItems(self._connection_service.get_supported_databases())
          
    def _connect_signals(self):
        """Подключение сигналов."""
        self.check_button.clicked.connect(self._on_check_button_click)
        self.ok_button.clicked.connect(self._on_ok_button_click)
        self.cancel_button.clicked.connect(self._on_cancel_button_click)
        
    def _setup_ui(self):
        """Настройка UI."""
        DialogTranslator().translate(self, "CONNECTION_DIALOG")
    
    def _validate_fields(self):
        """Проверка заполненности полей."""
        if not self.name_edit.text():
            QMessageBox.warning(self, self.tr("warning_title"), 
                               self.tr("name_required"))
            return False
        
        if not self.address_edit.text():
            QMessageBox.warning(self, self.tr("warning_title"), 
                               self.tr("address_required"))
            return False
        
        if not self.port_edit.text():
            QMessageBox.warning(self, self.tr("warning_title"), 
                               self.tr("port_required"))
            return False
        
        if not self.database_edit.text():
            QMessageBox.warning(self, self.tr("warning_title"), 
                               self.tr("database_required"))
            return False
        
        if not self.username_edit.text():
            QMessageBox.warning(self, self.tr("warning_title"), 
                               self.tr("username_required"))
            return False
        
        # Пароль может быть пустым для некоторых типов аутентификации
        return True
    
    def _on_check_button_click(self):
        """Обработчик кнопки проверки подключения."""
        # Проверка заполненности полей
        if not self._validate_fields():
            return
        
        # Получение данных из полей ввода
        db_type = self.dbms_combo.currentText()
        name = self.name_edit.text()
        host = self.address_edit.text()
        port = self.port_edit.text()
        database = self.database_edit.text()
        username = self.username_edit.text()
        password = self.password_edit.text()

        # Создание DTO с параметрами подключения
        config = ConnectionConfigDTO(
            db_type=db_type,
            name=name,
            host=host,
            port=port,
            database=database,
            username=username,
            password=password
        )

        # Проверка подключения
        try:
            result = self._session.connect(config)
            if result.is_success:
                self._session.close()
                QMessageBox.information(self, self.tr("success_title"), 
                                      self.tr("connection_successful"))
            else:
                QMessageBox.critical(self, self.tr("error_title"), 
                                   self.tr("connection_failed", result.error))
        except Exception as e:
            QMessageBox.critical(self, self.tr("error_title"), 
                               self.tr("connection_check_error", str(e)))

    def _on_ok_button_click(self):
        """Обработчик кнопки OK для сохранения подключения."""
        # Проверка заполненности полей
        if not self._validate_fields():
            return
        
        name = self.name_edit.text()
        
        # Проверка существования подключения с таким именем
        existing_config = self._connection_service.get_config_by_name(name)
        if existing_config:
            reply = QMessageBox.question(
                self, 
                self.tr("confirmation_title"), 
                self.tr("connection_exists", name),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                return

        # Получение данных из полей ввода
        db_type = self.dbms_combo.currentText()
        host = self.address_edit.text()
        port = self.port_edit.text()
        database = self.database_edit.text()
        username = self.username_edit.text()
        password = self.password_edit.text()

        # Создание DTO с параметрами подключения
        config = ConnectionConfigDTO(
            db_type=db_type,
            name=name,
            host=host,
            port=port,
            database=database,
            username=username,
            password=password
        )

        # Сохранение конфигурации
        result = self._connection_service.save_config(config)
        if result.is_fail:
            QMessageBox.critical(self, self.tr("error_title"), 
                self.tr("save_error", result.error))
            return
    
        self.accept()

    def _on_cancel_button_click(self):
        """Обработчик кнопки Отмена."""
        self.reject()
        
    def set_connection_data(self, config: ConnectionConfigDTO):
        """Заполнение полей диалога данными существующего подключения."""
        self.name_edit.setText(str(config.name) if config.name else "")
        self.address_edit.setText(str(config.host) if config.host else "")
        self.port_edit.setText(str(config.port) if config.port else "")
        self.database_edit.setText(str(config.database) if config.database else "")
        self.username_edit.setText(str(config.username) if config.username else "")
        self.password_edit.setText(str(config.password) if config.password else "")
        
        # Установка типа БД в комбобоксе
        index = self.dbms_combo.findText(config.db_type)
        if index >= 0:
            self.dbms_combo.setCurrentIndex(index)