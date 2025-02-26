from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox, QCheckBox
from qgis.PyQt.QtCore import Qt

from ..localization.localization_manager import LocalizationManager

class CredentialsDialog(QDialog):
    """Диалог для ввода учетных данных"""
    
    def __init__(self, conn_name, parent=None, default_username=None):
        super().__init__(parent)
        self.lm = LocalizationManager.instance()  # Инициализация менеджера локализации
        self.setWindowTitle(self.lm.get_string("CREDENTIALS_DIALOG", "title", conn_name))
        self.default_username = default_username
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Username input
        self.username_label = QLabel(self.lm.get_string("CREDENTIALS_DIALOG", "username_label"))
        self.username_input = QLineEdit()
        if self.default_username:
            self.username_input.setText(self.default_username)
        layout.addWidget(self.username_label)
        layout.addWidget(self.username_input)

        # Password input
        self.password_label = QLabel(self.lm.get_string("CREDENTIALS_DIALOG", "password_label"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_input)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Ok).setText(self.lm.get_string("COMMON", "confirm"))
        buttons.button(QDialogButtonBox.Cancel).setText(self.lm.get_string("COMMON", "cancel"))
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_credentials(self):
        """Возвращает введенные учетные данные"""
        return self.username_input.text(), self.password_input.text()

    @staticmethod
    def get_credentials_for_connection(conn_name, parent=None, default_username=None):
        """Статический метод для получения учетных данных"""
        dialog = CredentialsDialog(conn_name, parent, default_username)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_credentials()
        return None, None
