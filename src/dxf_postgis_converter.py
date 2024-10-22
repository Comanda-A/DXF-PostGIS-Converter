
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import Qgis

from ..src.draw.DrawRect import RectangleMapTool
from ..src.draw.DrawCircle import CircleMapTool
from ..src.draw.DrawPolygon import PolygonMapTool
from ..src.logger.logger import Logger
from ..src.plugins.dxf_tools.clsADXF2Shape import clsADXF2Shape

from .gui.main_dialog import ConverterDialog
from .. import resources
import os.path


class DxfPostGISConverter:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.subplugin = None

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'Converter_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.translate_string(u'&DXF-PostGIS Converter')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None


    def translate_string(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
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
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = ':/plugins/coco/icon.png'
        self.add_action(
            icon_path,
            text=self.translate_string(u'DXF-PostGIS Converter'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.translate_string(u'&DXF-PostGIS Converter'),
                action)
            self.iface.removeToolBarIcon(action)


    def selectArea(self):
        self.dlg.hide()
        if self.dlg.type_shape.currentText() == 'rect':
            self.rect = RectangleMapTool(self.canvas, self.dlg)
            self.iface.mapCanvas().setMapTool(self.rect)
        elif self.dlg.type_shape.currentText() == 'circle':
            self.circle = CircleMapTool(self.canvas, self.dlg)
            self.iface.mapCanvas().setMapTool(self.circle)
        elif self.dlg.type_shape.currentText() == 'polygon':
            self.polygon = PolygonMapTool(self.canvas, self.dlg)
            self.iface.mapCanvas().setMapTool(self.polygon)

        self.iface.messageBar().pushMessage("Подсказка", "Выделите желаемую область для импорта", level=Qgis.Info, duration=5)
        self.iface.messageBar().pushMessage("Предупреждение", "Выделение работает с ПЕРВОЙ АКТИВНОЙ группой слоев", level=Qgis.Warning, duration=3)

    def run_subplugin(self):
        """Запуск подплагина"""
        self.subplugin = clsADXF2Shape(self.dlg)
        self.subplugin.run()

    def run(self):
        """Run method that performs all the real work"""
        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start:
            self.first_start = False
            self.dlg = ConverterDialog()
            self.dlg.select_area_button.clicked.connect(self.selectArea)
            self.dlg.open_dxf_button.clicked.connect(self.run_subplugin)
            self.dlg.select_area_button.setEnabled(self.dlg.dxf_handler.file_is_open)

        self.dlg.settings_statusLabel.setText("No connect")
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass