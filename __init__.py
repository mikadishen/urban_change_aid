# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Urban Change AID
                                 A QGIS Plugin
 Análise e detecção de mudanças urbanas assistida por IA

                              -------------------
        begin                : 2025-11-07
        copyright            : (C) 2025 by Leandro da Silva Gregorio
        email                : 
        license              : GPL v3
 ***************************************************************************/

Este programa é software livre: você pode redistribuí-lo e/ou modificá-lo
sob os termos da Licença Pública Geral GNU conforme publicada pela Free
Software Foundation, tanto a versão 3 da Licença como (a seu critério)
qualquer versão posterior.

Este programa é distribuído na esperança de que seja útil, mas SEM
QUALQUER GARANTIA; sem mesmo a garantia implícita de COMERCIALIZAÇÃO ou
ADEQUAÇÃO A UM DETERMINADO PROPÓSITO. Consulte a Licença Pública Geral GNU
para mais detalhes.

Você deve ter recebido uma cópia da Licença Pública Geral GNU
junto com este programa. Caso contrário, veja <https://www.gnu.org/licenses/>.
"""


def classFactory(iface):
    """
    Load UrbanChangeAid class from file urban_change_aid.py
    
    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .urban_change_aid import UrbanChangeAid
    return UrbanChangeAid(iface)

