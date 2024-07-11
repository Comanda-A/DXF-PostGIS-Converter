# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Converter
                                 A QGIS plugin
 Конвертирует туда сюда
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2024-06-29
        copyright            : (C) 2024 by command A, power PI
        email                : unknown
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load Converter class from file Converter.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .Dxf_Pgsql_Converter import Dxf_Pgsql_Converter
    return Dxf_Pgsql_Converter(iface)
