# -*- coding: utf-8 -*-
"""Test UI loading"""
from PyQt5 import QtWidgets, uic
import sys

app = QtWidgets.QApplication(sys.argv)

ui_file = r'c:\Users\nikita\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\DXF-PostGIS-Converter\src\presentation\resources\main_dialog.ui'
form_class, _ = uic.loadUiType(ui_file)

class TestDialog(QtWidgets.QDialog, form_class):
    pass

dialog = TestDialog()
dialog.setupUi(dialog)

print('Has layer_filter_list:', hasattr(dialog, 'layer_filter_list'))
print('Filter attributes:', [x for x in dir(dialog) if 'filter' in x.lower()])
print('All widgets:', [x for x in dir(dialog) if not x.startswith('_') and hasattr(getattr(dialog, x), 'setEnabled')])[:20]
