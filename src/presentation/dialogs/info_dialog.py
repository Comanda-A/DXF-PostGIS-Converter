from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QTextBrowser, 
                           QPushButton, QScrollArea, QWidget)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

class InfoDialog(QDialog):
    """
    Многоразовый диалог для отображения форматированной справочной информации.
    
    Параметры:
    -----------
    title : str
        Заголовок диалогового окна
    content : str
        HTML-форматированный контент для отображения
    parent : QWidget, optional
        Родительский виджет для диалога
    width : int, optional
        Начальная ширина диалога (по умолчанию: 800)
    height : int, optional
        Начальная высота диалога (по умолчанию: 600)
    is_html : bool, optional
        True если контент это HTML, False если обычный текст (по умолчанию: True)
    """
    
    def __init__(self, title, content, parent=None, width=800, height=600, is_html=True):
        super().__init__(parent)
        self.title = title
        self.content = content
        self.default_width = width
        self.default_height = height
        self.is_html = is_html
        self.setup_ui()
        
    def setup_ui(self):
        """Инициализация пользовательского интерфейса"""
        # Установка свойств окна
        self.setWindowTitle(self.title)
        self.setMinimumWidth(self.default_width)
        self.setMinimumHeight(self.default_height)
        
        # Установка иконки окна, если доступна
        self.setWindowIcon(QIcon(":/plugins/DXFPostGIS/icon.png"))
        
        # Создание основного layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Создание прокручиваемой текстовой области
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Создание и настройка текстового браузера
        text_widget = QTextBrowser()
        text_widget.setOpenExternalLinks(True)
        
        # Выбираем метод отображения в зависимости от типа контента
        if self.is_html:
            text_widget.setHtml(self.content)
        else:
            # Для обычного текста используем setPlainText
            text_widget.setPlainText(self.content)
            # Используем монопространственный шрифт для отчетов
            from PyQt5.QtGui import QFont
            font = QFont()
            font.setFamily("Courier New")
            font.setPointSize(9)
            text_widget.setFont(font)
        
        text_widget.setStyleSheet("""
            QTextBrowser {
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        
        scroll.setWidget(text_widget)
        layout.addWidget(scroll)
        
        # Добавление кнопки закрытия
        close_button = QPushButton("Закрыть")
        close_button.setStyleSheet("""
            QPushButton {
                min-width: 80px;
                padding: 5px;
                background-color: #007bff;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignRight)
