from qgis.PyQt import QtGui
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                                QPushButton, QLabel, QGraphicsView, 
                                QGraphicsScene, QWidget)
from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtSvg import QGraphicsSvgItem, QSvgWidget
import os
from ..logger.logger import Logger

class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        """Инициализирует ZoomableGraphicsView с поддержкой масштабирования."""
        super().__init__(parent)
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.zoom_factor = 1.15

    def wheelEvent(self, event):
        """Обрабатывает событие колесика мыши для масштабирования при зажатом Ctrl."""
        if event.modifiers() == Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                factor = self.zoom_factor
            else:
                factor = 1 / self.zoom_factor
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Обрабатывает двойной клик левой кнопкой для сброса вида."""
        if event.button() == Qt.LeftButton:
            self.resetView()

    def resetView(self):
        """Сбрасывает преобразование вида и подгоняет отображаемую область."""
        self.setTransform(QtGui.QTransform())
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)

class PreviewDialog(QDialog):
    def __init__(self, svg_path, parent=None):
        """Инициализирует диалог предпросмотра с указанным SVG файлом."""
        super().__init__(parent)
        self.setWindowTitle("DXF Preview")
        self.resize(800, 600)
        self.setup_ui(svg_path)

    def setup_ui(self, svg_path):
        """Настраивает пользовательский интерфейс диалога предпросмотра."""
        layout = QVBoxLayout(self)
        
        toolbar = QHBoxLayout()
        instructions = self.create_instructions()
        toolbar.addWidget(self.create_control_buttons())
        toolbar.addStretch()
        toolbar.addWidget(instructions)
        
        self.setup_svg_view(svg_path)
        
        layout.addLayout(toolbar)
        layout.addWidget(self.view)
        
        self.reset_view()

    def create_instructions(self):
        """Создает метку с инструкциями по управлению предпросмотром."""
        instructions = QLabel(
            "🖱️ Управление:\n"
            "• Ctrl + колесо мыши - масштабирование\n"
            "• Зажать ЛКМ - перемещение\n"
            "• Двойной клик - сброс вида\n"
            "• Ctrl + (+/-) - масштабирование\n"
            "• Ctrl + 0 - сброс вида\n"
            "• Esc - закрыть"
        )
        instructions.setStyleSheet("color: #666; font-size: 10px;")
        return instructions

    def create_control_buttons(self):
        """Создает панель кнопок управления предпросмотром."""
        container = QWidget()
        layout = QHBoxLayout(container)
        
        buttons = [
            ("⟲", "Сбросить вид", lambda: self.reset_view()),
            ("➕", "Приблизить", lambda: self.zoom(1.2)),
            ("➖", "Отдалить", lambda: self.zoom(0.8))
        ]
        
        for text, tooltip, callback in buttons:
            btn = QPushButton(text)
            btn.setToolTip(tooltip)
            btn.clicked.connect(callback)
            btn.setFixedSize(30, 30)
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 16px;
                    border: 1px solid #ccc;
                    border-radius: 15px;
                    background-color: #f8f9fa;
                }
                QPushButton:hover {
                    background-color: #e9ecef;
                }
            """)
            layout.addWidget(btn)
        
        layout.setContentsMargins(0, 0, 0, 0)
        return container

    def setup_svg_view(self, svg_path):
        """Настраивает графическую сцену для отображения SVG."""
        self.scene = QGraphicsScene()
        self.view = ZoomableGraphicsView()
        self.view.setScene(self.scene)
        
        self.svg_item = QGraphicsSvgItem(svg_path)
        self.scene.addItem(self.svg_item)
        self.scene.setSceneRect(self.svg_item.boundingRect())

    def reset_view(self):
        """Сбрасывает вид предпросмотра."""
        self.view.resetView()

    def zoom(self, factor):
        """Масштабирует вид предпросмотра с заданным коэффициентом."""
        self.view.scale(factor, factor)

    def keyPressEvent(self, event):
        """Обрабатывает нажатия клавиш: Escape закрывает диалог, Ctrl+(+/-/0) масштабирует или сбрасывает вид."""
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.modifiers() == Qt.ControlModifier:
            if event.key() in (Qt.Key_Plus, Qt.Key_Equal):
                self.zoom(1.2)
            elif event.key() == Qt.Key_Minus:
                self.zoom(0.8)
            elif event.key() == Qt.Key_0:
                self.reset_view()
        else:
            super().keyPressEvent(event)

class PreviewWidgetFactory:
    def __init__(self):
        """Инициализирует фабрику виджетов предпросмотра с кешированием созданных виджетов."""
        self.preview_cache = {}

    def clear_cache(self):
        """Очищает кеш виджетов предпросмотра."""
        for widget in self.preview_cache.values():
            if widget and not widget.isDestroyed():
                widget.deleteLater()
        self.preview_cache.clear()

    def remove_from_cache(self, preview_path):
        """Удаляет конкретный виджет из кеша."""
        if preview_path in self.preview_cache:
            widget = self.preview_cache.pop(preview_path)
            if widget and not widget.isDestroyed():
                widget.deleteLater()

    def create_preview_widget(self, file_name, plugin_root_dir, on_preview_click):
        """Создает виджет предпросмотра для заданного файла."""
        preview_dir = os.path.join(plugin_root_dir, 'previews')
        preview_path = os.path.join(preview_dir, f"{os.path.splitext(file_name)[0]}.svg")
        
        Logger.log_message(f"Поиск предпросмотра по пути: {preview_path}")
        
        if not os.path.exists(preview_path):
            Logger.log_warning(f"Предпросмотр не найден по пути: {preview_path}")
            return None

        # Если виджет уже есть в кеше и не был удален, используем его
        if preview_path in self.preview_cache:
            cached_widget = self.preview_cache[preview_path]
            if cached_widget and not cached_widget.isDestroyed():
                return cached_widget
            else:
                # Если виджет был удален, удаляем его из кеша
                self.remove_from_cache(preview_path)

        try:
            container = QWidget()
            layout = QHBoxLayout(container)
            
            preview = QSvgWidget(preview_path)
            preview.setFixedSize(QSize(80, 80))
            
            expand_btn = QPushButton("🔍")
            expand_btn.setFixedSize(20, 20)
            expand_btn.clicked.connect(lambda: on_preview_click(preview_path))
            
            layout.addWidget(preview)
            layout.addWidget(expand_btn)
            layout.setContentsMargins(5, 5, 5, 5)
            layout.setSpacing(2)
            container.setLayout(layout)
            
            self.preview_cache[preview_path] = container
            return container
        except Exception as e:
            Logger.log_error(f"Ошибка создания виджета предпросмотра: {str(e)}")
            return None
