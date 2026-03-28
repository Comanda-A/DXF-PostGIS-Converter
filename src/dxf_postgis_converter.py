"""
DXF-PostGIS Converter Plugin Entry Point
"""

class DxfPostGISConverter:
    """
    QGIS Plugin Implementation.
    """

    def __init__(self, iface):
        # Core references
        self.iface = iface
        self.canvas = self.iface.mapCanvas()

        # State
        self.actions = []
        self.first_start = None
        self.dlg = None
        
        from . import Container
        Container.configure_di()

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
        from qgis.PyQt.QtGui import QIcon
        from qgis.PyQt.QtWidgets import QAction

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
            self.iface.addPluginToMenu('DXF-PostGIS Converter', action)

        self.actions.append(action)
        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = ':/plugins/coco/icon.png'
        self.add_action(
            icon_path,
            text='DXF-PostGIS Converter',
            callback=self.run,
            parent=self.iface.mainWindow()
        )
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                'DXF-PostGIS Converter',
                action
            )
            self.iface.removeToolBarIcon(action)
        
        # Cleanup container if needed
        # DependencyContainer handles its own cleanup

    def run(self):
        """Run method that performs all the real work."""

        # Create the dialog only once
        if self.first_start:
            self.first_start = False
            
            # Create dialog with DI container
            from .presentation.dialogs import ConverterDialog
            self.dlg = ConverterDialog(
                self.iface
            )

        # Show the dialog
        result = self.dlg.exec_()
        
        if result:
            # Dialog was accepted
            pass