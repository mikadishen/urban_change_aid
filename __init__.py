"""
Urban Change Detection Aid Plugin for QGIS

This plugin provides tools for detecting urban changes between two time periods
using satellite or aerial imagery.

Author: [Leandro Gregorio]
Date: [Current Date]
Version: 1.0
"""

def classFactory(iface):
    """
    Load UrbanChangeAid class from file urban_change_aid.py
    
    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .urban_change_aid import UrbanChangeAid
    return UrbanChangeAid(iface)

