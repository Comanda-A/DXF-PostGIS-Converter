# -*- coding: utf-8 -*-
"""
DXF-PostGIS Converter Plugin Entry Point (Refactored)

Использует DependencyContainer для инициализации зависимостей.
"""

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import Qgis

from ..src.draw.DrawRect import RectangleMapTool
from ..src.draw.DrawCircle import CircleMapTool
from ..src.draw.DrawPolygon import PolygonMapTool
from ..src.plugins.dxf_tools.clsADXF2Shape import clsADXF2Shape
from ..src.localization.localization_manager import LocalizationManager
from ..src.container import DependencyContainer
from ..src.logger.logger import Logger

# Используем рефакторированный диалог
from .gui.main_dialog_refactored import ConverterDialogRefactored
from .. import resources

import os.path


class DxfPostGISConverterRefactored:
    """
    QGIS Plugin Implementation (Refactored).
    
    Использует DI-контейнер для управления зависимостями.
    """

    def __init__(self, iface):
        """
        Constructor.

        :param iface: QGIS interface instance
        :type iface: QgsInterface
        """
        # Core references
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        
        # Initialize DI container
        self._container = DependencyContainer.instance()
        
        # Localization
        self.localization = LocalizationManager.instance()
        
        # Plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        
        # Initialize locale
        locale = QSettings().value('locale/userLocale', 'en')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            f'Converter_{locale}.qm'
        )
        
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)
        
        # State
        self.actions = []
        self.menu = self.translate_string('&DXF-PostGIS Converter')
        self.first_start = None
        self.dlg = None
        self.subplugin = None
        
        Logger.log_message("DxfPostGISConverter (refactored) initialized")

    def translate_string(self, message: str) -> str:
        """Get translation for a string."""
        return QCoreApplication.translate('Converter', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None
    ):
        """Add a toolbar icon to the toolbar."""
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip:
            action.setStatusTip(status_tip)

        if whats_this:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = ':/plugins/coco/icon.png'
        self.add_action(
            icon_path,
            text=self.translate_string('DXF-PostGIS Converter'),
            callback=self.run,
            parent=self.iface.mainWindow()
        )
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.translate_string('&DXF-PostGIS Converter'),
                action
            )
            self.iface.removeToolBarIcon(action)
        
        # Cleanup container if needed
        # DependencyContainer handles its own cleanup

    def selectArea(self):
        """Handle area selection for import."""
        ui = self.localization.strings.UI
        common = self.localization.strings.COMMON

        if self.dlg.check_selected_file():
            self.dlg.hide()
            shape_type = self.dlg.type_shape.currentText()

            if shape_type == ui["shape_rectangle"]:
                tool = RectangleMapTool(self.canvas, self.dlg)
            elif shape_type == ui["shape_circle"]:
                tool = CircleMapTool(self.canvas, self.dlg)
            elif shape_type == ui["shape_polygon"]:
                tool = PolygonMapTool(self.canvas, self.dlg)
            else:
                Logger.log_warning(f"Unknown shape type: {shape_type}")
                return

            self.iface.mapCanvas().setMapTool(tool)
            
            self.iface.messageBar().pushMessage(
                common["info"],
                ui.get("select_area_prompt", "Выделите желаемую область для импорта"),
                level=Qgis.Info,
                duration=5
            )
        else:
            self.iface.messageBar().pushMessage(
                common["warning"],
                ui.get("no_file_selected", "Файл не выбран, выберите файл в дереве"),
                level=Qgis.Warning,
                duration=5
            )

    def run_subplugin(self):
        """Run DXF import subplugin."""
        self.subplugin = clsADXF2Shape(self.dlg)
        self.subplugin.run()

    def run(self):
        """Run method that performs all the real work."""
        # Create the dialog only once
        if self.first_start:
            self.first_start = False
            
            # Create refactored dialog with DI container
            self.dlg = ConverterDialogRefactored(
                self.iface,
                container=self._container
            )
            
            # Connect signals
            self.dlg.select_area_button.clicked.connect(self.selectArea)
            self.dlg.open_dxf_button.clicked.connect(self.run_subplugin)
            self.dlg.select_area_button.setEnabled(self.dlg.dxf_handler.file_is_open)
            
            Logger.log_message("Main dialog created")

        # Show the dialog
        self.dlg.show()
        result = self.dlg.exec_()
        
        if result:
            # Dialog was accepted
            pass
